"""Model calls: retry policy, response validation, and the verification pass.

Three things here matter for reliability:
  * every transient failure is retried with backoff, and a permanent failure
    is recorded rather than swallowed;
  * model output is schema-checked, and malformed JSON gets one repair attempt
    before the task is marked failed;
  * `--fake` runs the entire pipeline with a deterministic stub so you can
    test scope, chunking, dedupe and reporting without spending anything.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from anthropic import Anthropic
    from anthropic.types import Message

    from .discover import Chunk

import hashlib
import json
import random
import re
import threading
import time
from dataclasses import dataclass
from typing import cast

from readthrough.types import Finding, Json

from .lenses import CONFIDENCES, LENSES, SEVERITIES, SYSTEM_PROMPT, USER_TEMPLATE, VERIFY_SYSTEM, VERIFY_TEMPLATE

MAX_ATTEMPTS = 5
BASE_BACKOFF = 2.0

# Thinking depth, lowest to highest. The fixed token budget these replaced
# was removed from the API; asking for one now returns a 400.
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")

# Floor for max_tokens once thinking is on, because the ceiling covers the
# thinking and the reply together.
THINKING_MAX_TOKENS = 16000

RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504, 529}


class PermanentError(Exception):
    """Not worth retrying (bad request, auth, malformed beyond repair)."""


@dataclass
class Usage:
    in_tokens: int = 0
    out_tokens: int = 0

    def add(self, other: Usage) -> None:
        self.in_tokens += other.in_tokens
        self.out_tokens += other.out_tokens


def _clean(item: Finding, key: str) -> str | None:
    """A model-supplied string field, or None when it said nothing.

    At module scope rather than nested in the parse loop: closing over the loop
    variable is a bug waiting for the day someone stores the callable.
    """
    v = item.get(key)
    return str(v).strip() if v not in (None, "", "null") else None


def _as_json(value: object) -> Json | None:
    """A decoded JSON value as an object, or None when it is anything else.

    json.loads only ever produces str keys, so the cast states what the decoder
    guarantees and cannot state in its own return type.
    """
    return cast("Json", value) if isinstance(value, dict) else None


def _extract_json(text: str) -> Json | None:  # noqa: PLR0912 — one branch per shape the model returns
    """Pull a JSON object out of a response that may have stray wrapping."""
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t).strip()
    try:
        return _as_json(json.loads(t))
    except json.JSONDecodeError:
        pass
    # Fall back to the first balanced object in the text.
    start = t.find("{")
    if start == -1:
        return None
    depth, in_str, esc = 0, False, False
    for i in range(start, len(t)):
        ch = t[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return _as_json(json.loads(t[start : i + 1]))
                except json.JSONDecodeError:
                    return None
    return None


def _clean_findings(obj: Json, lens_id: str, lo: int, hi: int) -> list[Finding]:
    """Validate and normalise. Anything unusable is dropped, not guessed at."""
    raw: object = obj.get("findings")
    if not isinstance(raw, list):
        return []
    raw_items: list[object] = raw  # pyright: ignore[reportUnknownVariableType]
    lens = LENSES[lens_id]
    out: list[Finding] = []
    for raw_item in raw_items:
        # The model wrote this: every field below is coerced or dropped, and
        # anything that is not an object at all is not a finding.
        item = _as_json(raw_item)
        if item is None:
            continue
        title = str(item.get("title") or "").strip()
        expl = str(item.get("explanation") or "").strip()
        if not title or not expl:
            continue
        try:
            s = int(item["start_line"])
            e = int(item.get("end_line", s))
        except (KeyError, TypeError, ValueError):
            continue
        if e < s:
            s, e = e, s
        # A line range outside the window shown is a hallucinated location.
        if s < lo or s > hi:
            continue
        e = min(max(e, s), hi)

        sev = str(item.get("severity") or "").lower().strip()
        if sev not in SEVERITIES:
            sev = "medium"
        conf = str(item.get("confidence") or "").lower().strip()
        if conf not in CONFIDENCES:
            conf = "medium"
        cat = str(item.get("category") or "").lower().strip()
        if cat not in lens.categories:
            cat = lens.categories[-1] if lens.categories else lens_id

        out.append({
            "title": title[:200], "category": cat, "severity": sev,
            "confidence": conf, "start_line": s, "end_line": e,
            "symbol": _clean(item, "symbol"), "explanation": expl,
            "trigger": _clean(item, "trigger"), "assumptions": _clean(item, "assumptions"),
            "suggested_fix": _clean(item, "suggested_fix"),
            "suggested_test": _clean(item, "suggested_test"),
        })
    return out


class Engine:
    def __init__(self, model: str, max_tokens: int = 8000,
                 effort: str | None = None, fake: bool = False):
        self.model = model
        self.max_tokens = max_tokens
        self.effort = effort
        self.fake = fake
        # None on a fake run; _call_once refuses to run without it.
        self.client: Anthropic | None = None
        # Every distinct model that actually served a response. Behind a proxy
        # that rotates providers, an unknown model name silently falls through
        # to whatever is next in the pool, so the requested model is not
        # evidence of what ran. The report states both.
        self.served_models: set[str] = set()
        self._served_lock = threading.Lock()
        # One task runs on one worker thread at a time, so thread-local is
        # enough to attribute a task to the model that answered it without
        # threading a return value through every call site.
        self._local = threading.local()
        if not fake:
            from anthropic import Anthropic  # noqa: PLC0415 — optional dependency, imported on first use
            self.client = Anthropic(max_retries=0)  # we own the retry policy

    # ---- transport ------------------------------------------------------
    def _call_once(self, system: str, user: str) -> tuple[str, Usage]:
        kwargs: Json = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        if self.effort:
            # Adaptive thinking with an effort level, not a token budget: the
            # current models reject `thinking: {"type": "enabled",
            # "budget_tokens": N}` with a 400, and reject temperature/top_p/
            # top_k outright. Depth is an effort level now; style is prompting.
            kwargs["thinking"] = {"type": "adaptive"}
            kwargs["output_config"] = {"effort": self.effort}
            # max_tokens caps thinking *plus* the reply, so a ceiling sized for
            # the answer alone truncates mid-response once the model thinks.
            kwargs["max_tokens"] = max(self.max_tokens, THINKING_MAX_TOKENS)

        if self.client is None:
            msg = "this Engine was built with fake=True and has no client to call"
            raise RuntimeError(msg)
        # The optional arguments (thinking, effort) are assembled above,
        # so the call goes through **kwargs and the SDK's overloads cannot see
        # what it returns. It returns a Message.
        resp = cast("Message", self.client.messages.create(**kwargs))
        served = getattr(resp, "model", None)
        self._local.served = served
        if served:
            with self._served_lock:
                self.served_models.add(served)
        text = "".join(b.text for b in resp.content if b.type == "text")
        return text, Usage(resp.usage.input_tokens, resp.usage.output_tokens)

    def call(self, system: str, user: str) -> tuple[str, Usage]:
        if self.fake:
            return self._fake(system, user)

        import anthropic  # noqa: PLC0415 — optional dependency, imported on first use
        last = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                return self._call_once(system, user)
            except anthropic.APIStatusError as exc:
                last = exc
                status = getattr(exc, "status_code", None)
                if status not in RETRYABLE_STATUS:
                    raise PermanentError(f"HTTP {status}: {exc}") from exc
            except (anthropic.APIConnectionError, anthropic.APITimeoutError) as exc:
                last = exc
            except anthropic.AnthropicError as exc:
                raise PermanentError(str(exc)) from exc

            if attempt < MAX_ATTEMPTS - 1:
                # Retry jitter, not a secret
                delay = BASE_BACKOFF * (2 ** attempt) + random.uniform(0, 1.5)  # noqa: S311
                time.sleep(min(delay, 60))
        raise RuntimeError(f"exhausted {MAX_ATTEMPTS} attempts: {last}")

    @property
    def last_served(self) -> str | None:
        """The model that answered this thread's most recent call."""
        return getattr(self._local, "served", None)

    # ---- scanning -------------------------------------------------------
    def scan_chunk(self, chunk: Chunk, lens_id: str) -> tuple[list[Finding], Usage]:
        lens = LENSES[lens_id]
        chunk_note = ""
        context_note = "\n"
        if chunk.n_chunks > 1:
            chunk_note = (f"Section {chunk.chunk_idx + 1} of {chunk.n_chunks} "
                          f"(lines {chunk.start_line}-{chunk.end_line} of the file)")
            context_note = (
                "\nThis is a section of a larger file. Imports, helpers and "
                "guards may live outside the window. Report a finding only if "
                "the code shown is wrong regardless of what surrounds it, and "
                "put what you assumed in `assumptions`.\n")

        user = USER_TEMPLATE.format(
            lens_title=lens.title, lens_focus=lens.focus, path=chunk.rel,
            lang=chunk.lang, chunk_note=chunk_note, code=chunk.numbered,
            context_note=context_note,
            categories=", ".join(lens.categories),
        )

        usage = Usage()
        text, u = self.call(SYSTEM_PROMPT, user)
        usage.add(u)
        obj = _extract_json(text)

        if obj is None:
            repair = ("The following was supposed to be a single JSON object "
                      "with a \"findings\" array, but it did not parse. Return "
                      "the same information as valid JSON, nothing else. If it "
                      "contains no findings, return {\"findings\": []}.\n\n"
                      + text[:12000])
            text2, u2 = self.call(SYSTEM_PROMPT, repair)
            usage.add(u2)
            obj = _extract_json(text2)

        if obj is None:
            raise PermanentError("model did not return parseable JSON")

        return _clean_findings(obj, lens_id, chunk.start_line, chunk.end_line), usage

    # ---- verification ---------------------------------------------------
    def verify(self, finding: Finding, code: str) -> tuple[Finding, Usage]:
        user = VERIFY_TEMPLATE.format(
            path=finding["rel"], start_line=finding["start_line"],
            end_line=finding["end_line"], category=finding["category"],
            severity=finding["severity"], title=finding["title"],
            explanation=finding["explanation"],
            trigger=finding.get("trigger") or "(none given)", code=code,
        )
        text, usage = self.call(VERIFY_SYSTEM, user)
        obj = _extract_json(text) or {}
        verdict = str(obj.get("verdict", "uncertain")).lower().strip()
        if verdict not in {"confirmed", "rejected", "uncertain"}:
            verdict = "uncertain"
        sev = str(obj.get("corrected_severity", "")).lower().strip()
        if sev not in SEVERITIES:
            sev = finding["severity"]
        return {"verdict": verdict,
                "reasoning": str(obj.get("reasoning", "")).strip(),
                "severity": sev}, usage

    # ---- offline stub ---------------------------------------------------
    def _fake(self, system: str, user: str) -> tuple[str, Usage]:
        """Deterministic stub. Exercises the full pipeline for free."""
        seed = int(hashlib.sha256(user.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)  # noqa: S311 — reproducible sampling, not a secret

        if "Claimed finding" in user:
            v = rng.choice(["confirmed", "confirmed", "rejected", "uncertain"])
            return (json.dumps({"verdict": v, "reasoning": "stub verdict",
                                "corrected_severity": "high"}),
                    Usage(1200, 200))

        m = re.search(r"^\s*(\d+)\|", user, re.M)
        first = int(m.group(1)) if m else 1
        nums = [int(x) for x in re.findall(r"^\s*(\d+)\|", user, re.M)] or [first]
        lens_id = next((lid for lid in LENSES if LENSES[lid].title in user), "logic")
        cats = LENSES[lens_id].categories or (lens_id,)

        findings: list[Finding] = []
        for _ in range(rng.choice([0, 0, 1, 1, 2])):
            ln = rng.choice(nums)
            findings.append({
                "title": f"stub {lens_id} finding at line {ln}",
                "category": rng.choice(cats),
                "severity": rng.choice(SEVERITIES),
                "confidence": rng.choice(CONFIDENCES),
                "start_line": ln, "end_line": min(ln + 3, max(nums)),
                "symbol": "stub_fn",
                "explanation": "Synthetic finding produced by --fake mode.",
                "trigger": "n/a", "assumptions": None,
                "suggested_fix": "n/a", "suggested_test": "n/a",
            })
        return json.dumps({"findings": findings}), Usage(3000, 400)
