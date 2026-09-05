"""Report generation.

The coverage section comes first and is the point of the whole thing: it says
what was scanned, what was skipped and why, and what failed. A findings list
without that is unfalsifiable -- you cannot tell "clean" from "never looked".
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .store import Store

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .merge import merge_findings, priority_score

SEV_LABEL = {"critical": "CRITICAL", "high": "HIGH",
             "medium": "MEDIUM", "low": "LOW"}


# Past this many, the uncovered-files list stops being readable.
MAX_UNCOVERED_LISTED = 60


def build_results(store: Store) -> dict:
    files = [dict(r) for r in store.files()]
    tasks = [dict(r) for r in store.tasks()]
    merged = merge_findings(store.raw_findings())

    verdicts = store.verdicts()
    for f in merged:
        v = verdicts.get(f["fingerprint"])
        if v:
            f["verdict"] = v["verdict"]
            f["verdict_reasoning"] = v["reasoning"]
            if v["severity"]:
                f["severity"] = v["severity"]
    merged.sort(key=lambda f: (-priority_score(f), f["rel"], f["start_line"]))

    scanned_rels = {t["rel"] for t in tasks if t["status"] == "done"}
    failed_tasks = [t for t in tasks if t["status"] != "done"]
    failed_rels = {t["rel"] for t in failed_tasks}

    candidates = [f for f in files if f["status"] == "pending"]
    skipped = [f for f in files if f["status"] == "skipped"]
    not_started = [f for f in candidates
                   if f["rel"] not in scanned_rels and f["rel"] not in failed_rels]
    partial = sorted(failed_rels & scanned_rels)
    uncovered = sorted(failed_rels - scanned_rels)

    in_tok, out_tok = store.token_totals()

    return {
        "meta": {
            "root": store.get_meta("root"),
            "model": store.get_meta("model"),
            "served_models": store.get_meta("served_models", []),
            "lenses": store.get_meta("lenses", []),
            "repeats": store.get_meta("repeats", 1),
            "verified": store.get_meta("verified", False),
            "started_at": store.get_meta("started_at"),
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        "coverage": {
            "files_discovered": len(files),
            "files_eligible": len(candidates),
            "files_scanned": len(scanned_rels),
            "files_skipped": len(skipped),
            "files_not_started": len(not_started),
            "files_partial": partial,
            "files_uncovered": uncovered,
            "tasks_total": len(tasks),
            "tasks_done": len(tasks) - len(failed_tasks),
            "tasks_failed": len(failed_tasks),
            "skipped_detail": [{"file": f["rel"], "reason": f["note"]}
                               for f in skipped],
            "not_started_detail": [f["rel"] for f in not_started],
            "failed_detail": [{"file": t["rel"], "lens": t["lens"],
                               "lines": f"{t['start_line']}-{t['end_line']}",
                               "attempts": t["attempts"],
                               "error": (t["error"] or "")[:300]}
                              for t in failed_tasks],
            "total_loc": sum(f["loc"] or 0 for f in candidates),
        },
        "usage": {"input_tokens": in_tok, "output_tokens": out_tok},
        "findings": merged,
    }


def _pct(n: float, d: float) -> str:
    return f"{(100.0 * n / d):.1f}%" if d else "n/a"


def render_markdown(  # noqa: PLR0912,PLR0915 — one section per report block, in order
res: dict, max_detail: int = 250) -> str:
    m, cov, use = res["meta"], res["coverage"], res["usage"]
    findings = res["findings"]
    active = [f for f in findings if f.get("verdict") != "rejected"]
    rejected = [f for f in findings if f.get("verdict") == "rejected"]

    sev_counts = Counter(f["severity"] for f in active)
    # Every model that produced a finding in this scan.db, across all runs that
    # built it. When there is more than one, each finding names its own.
    all_models = sorted({mo for f in findings for mo in (f.get("models") or [])})
    out = []
    add = out.append

    add(f"# Code audit: `{m['root']}`")
    add("")
    add(f"Generated {m['generated_at']} | model `{m['model']}` | "
      f"lenses: {', '.join(m['lenses'])} | repeats: {m['repeats']}"
      + (" | verification pass: on" if m.get("verified") else ""))
    add("")

    # The requested model is not evidence of what ran. A proxy may resolve an
    # alias (expected) or fall through to an unrelated provider (not), and a
    # report headed with a model that never answered is exactly the kind of
    # unearned claim this tool exists to avoid. State the fact, don't judge it.
    #
    # Note this covers only the models seen while building THIS scan.db. A
    # resumed scan keeps the findings of passes that an earlier run completed,
    # so the per-finding attribution below is the authoritative one.
    served = [s for s in m.get("served_models", []) if s != m["model"]]
    if served:
        add(f"> **Requested `{m['model']}`; answered by "
          f"{', '.join(f'`{s}`' for s in served)}.** A proxy may be resolving "
          f"an alias, or falling through to a different model entirely — judge "
          f"the findings against whatever actually answered. Passes cached "
          f"from an earlier run keep the model that answered *them*; each "
          f"finding names its own below.")
        add("")

    # -- coverage ------------------------------------------------------
    add("## Coverage")
    add("")
    add("| | |")
    add("|---|---|")
    add(f"| Files discovered | {cov['files_discovered']} |")
    add(f"| Eligible for review | {cov['files_eligible']} "
      f"({cov['total_loc']:,} lines) |")
    add(f"| Scanned | {cov['files_scanned']} "
      f"({_pct(cov['files_scanned'], cov['files_eligible'])}) |")
    add(f"| Skipped by filter | {cov['files_skipped']} |")
    add(f"| Never started | {cov['files_not_started']} |")
    add(f"| Passes run | {cov['tasks_done']} of {cov['tasks_total']} |")
    add(f"| Passes failed | {cov['tasks_failed']} |")
    add(f"| Tokens | {use['input_tokens']:,} in / {use['output_tokens']:,} out |")
    add("")

    if cov["files_uncovered"]:
        add("> **Gaps.** These files produced no successful pass and are "
          "therefore unreviewed:")
        add("> ")
        for r in cov["files_uncovered"][:60]:
            add(f"> - `{r}`")
        if len(cov["files_uncovered"]) > MAX_UNCOVERED_LISTED:
            add(f"> - ... and {len(cov['files_uncovered']) - 60} more")
        add("")
    if cov["files_partial"]:
        add(f"> **Partial.** {len(cov['files_partial'])} files had at least one "
          "pass fail; see the appendix. Their results are incomplete.")
        add("")
    if cov["files_not_started"]:
        add(f"> **Not started.** {cov['files_not_started']} eligible files were "
          "never queued (run interrupted?). Re-run the same command to finish.")
        add("")

    # -- summary -------------------------------------------------------
    add("## Findings summary")
    add("")
    if not active:
        add("No findings survived merging and verification.")
        add("")
    else:
        add("| Severity | Count |")
        add("|---|---|")
        for sev in ("critical", "high", "medium", "low"):
            if sev_counts.get(sev):
                add(f"| {SEV_LABEL[sev]} | {sev_counts[sev]} |")
        add(f"| **Total** | **{len(active)}** |")
        add("")
        if rejected:
            add(f"{len(rejected)} additional findings were rejected by the "
              "verification pass and are listed in the appendix.")
            add("")

        by_file = Counter(f["rel"] for f in active)
        add("**Files with the most findings**")
        add("")
        add("| File | Findings |")
        add("|---|---|")
        for rel, n in by_file.most_common(12):
            add(f"| `{rel}` | {n} |")
        add("")

        by_cat = Counter(f["family"] for f in active)
        add("**Recurring defect classes** — these are the candidates for a "
          "Semgrep rule rather than a one-off fix.")
        add("")
        add("| Class | Count |")
        add("|---|---|")
        for cat, n in by_cat.most_common(15):
            add(f"| `{cat}` | {n} |")
        add("")

    # -- detail --------------------------------------------------------
    if active:
        add("## Findings")
        add("")
        for i, f in enumerate(active[:max_detail], 1):
            add(f"### {i}. {SEV_LABEL[f['severity']]} — {f['title']}")
            add("")
            loc = (f"`{f['rel']}`:{f['start_line']}"
                   + (f"-{f['end_line']}" if f["end_line"] != f["start_line"] else ""))
            total_passes = max(1, len(m["lenses"]) * m["repeats"])
            bits = [loc, f"class `{f['family']}`",
                    f"confidence {f['confidence']}",
                    f"agreement {f['agreement']}/{total_passes}"]
            if f.get("corroboration", 1) > f["agreement"]:
                bits.append(f"corroborated by {f['corroboration']} passes")
            if f.get("symbol"):
                bits.insert(1, f"in `{f['symbol']}`")
            if f.get("verdict"):
                bits.append(f"verification: {f['verdict']}")
            add(" · ".join(bits))
            add("")
            add(f["explanation"])
            add("")
            if f.get("trigger"):
                add(f"**Trigger.** {f['trigger']}")
                add("")
            if f.get("assumptions"):
                add(f"**Assumes.** {f['assumptions']}")
                add("")
            if f.get("suggested_fix"):
                add(f"**Fix.** {f['suggested_fix']}")
                add("")
            if f.get("suggested_test"):
                add(f"**Regression test.** {f['suggested_test']}")
                add("")
            if f.get("verdict_reasoning"):
                add(f"**Verification.** {f['verdict_reasoning']}")
                add("")
            if f.get("colocated_families"):
                add("**Also flagged at these lines.** "
                  + ", ".join(f"`{c}`" for c in f["colocated_families"])
                  + " — this range is worth reading in full rather than "
                    "patching one line.")
                add("")
            models = f.get("models") or []
            model_note = (f"model: {', '.join(models)} · "
                          if len(all_models) > 1 and models else "")
            add(f"<sub>found by: {', '.join(f['lenses'])} · {model_note}"
              f"fingerprint `{f['fingerprint']}`</sub>")
            add("")
            add("---")
            add("")
        if len(active) > max_detail:
            add(f"*{len(active) - max_detail} further findings omitted from this "
              "document; all of them are in `findings.json`.*")
            add("")

    # -- appendix ------------------------------------------------------
    add("## Appendix")
    add("")
    if cov["failed_detail"]:
        add("### Failed passes")
        add("")
        add("These passes did not complete. Re-running resumes them.")
        add("")
        add("| File | Lens | Lines | Attempts | Error |")
        add("|---|---|---|---|---|")
        for d in cov["failed_detail"][:100]:
            err = d["error"].replace("|", "\\|").replace("\n", " ")[:120]
            add(f"| `{d['file']}` | {d['lens']} | {d['lines']} | "
              f"{d['attempts']} | {err} |")
        add("")
    else:
        add("### Failed passes")
        add("")
        add("None. Every queued pass completed.")
        add("")

    if rejected:
        add("### Rejected by verification")
        add("")
        add("| File | Lines | Title | Why rejected |")
        add("|---|---|---|---|")
        for f in rejected[:80]:
            why = (f.get("verdict_reasoning") or "").replace("|", "\\|")[:160]
            add(f"| `{f['rel']}` | {f['start_line']}-{f['end_line']} | "
              f"{f['title'][:70]} | {why} |")
        add("")

    if cov["skipped_detail"]:
        add("### Skipped files")
        add("")
        reasons = Counter(d["reason"].split("(")[0].strip()
                          for d in cov["skipped_detail"])
        add("| Reason | Count |")
        add("|---|---|")
        for r, n in reasons.most_common():
            add(f"| {r} | {n} |")
        add("")
        add("<details><summary>Full list</summary>")
        add("")
        for d in cov["skipped_detail"][:400]:
            add(f"- `{d['file']}` — {d['reason']}")
        add("")
        add("</details>")
        add("")

    return "\n".join(out)


def write_reports(res: dict, outdir: Path) -> dict:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    md = outdir / "report.md"
    js = outdir / "findings.json"
    cv = outdir / "coverage.json"
    sr = outdir / "findings.sarif"

    md.write_text(render_markdown(res), encoding="utf-8")
    js.write_text(json.dumps(res, indent=2), encoding="utf-8")
    cv.write_text(json.dumps(res["coverage"], indent=2), encoding="utf-8")
    sr.write_text(json.dumps(to_sarif(res), indent=2), encoding="utf-8")
    return {"markdown": md, "json": js, "coverage": cv, "sarif": sr}


def to_sarif(res: dict) -> dict:
    """SARIF 2.1.0 so findings can be uploaded to GitHub code scanning."""
    level = {"critical": "error", "high": "error",
             "medium": "warning", "low": "note"}
    rules, seen = [], set()
    results = []
    for f in res["findings"]:
        if f.get("verdict") == "rejected":
            continue
        rid = f["family"]
        if rid not in seen:
            seen.add(rid)
            rules.append({
                "id": rid,
                "shortDescription": {"text": rid.replace("-", " ")},
                "defaultConfiguration": {"level": level.get(f["severity"], "warning")},
            })
        _lo = max(1, f["start_line"])
        results.append({
            "ruleId": rid,
            "level": level.get(f["severity"], "warning"),
            "message": {"text": f"{f['title']}\n\n{f['explanation']}"},
            "partialFingerprints": {"readthrough/v1": f["fingerprint"]},
            "locations": [{"physicalLocation": {
                "artifactLocation": {"uri": f["rel"]},
                # endLine clamps to startLine, not to 1. Clamping the two
                # independently can invert them, which is the one thing this
                # defensive code exists to prevent -- and SARIF consumers
                # reject endLine < startLine outright.
                "region": {"startLine": _lo, "endLine": max(_lo, f["end_line"])},
            }}],
        })
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {"name": "readthrough",
                                "informationUri": "https://example.invalid/readthrough",
                                "rules": rules}},
            "results": results,
        }],
    }
