"""Collapse duplicate findings across lenses, repeats and overlapping chunks.

The same defect surfaces at slightly different line ranges from different
passes, so bucketing by exact line fails. Instead: cluster findings in the
same file and category whose line ranges overlap or sit within a few lines of
each other, then merge each cluster into one finding.

Agreement -- how many independent passes reported the same cluster -- is the
single most useful signal for triage. A finding three passes agree on is
rarely noise; one reported once at low confidence usually is.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

PROXIMITY = 6  # lines; ranges this close are treated as the same defect

SEV_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
CONF_RANK = {"high": 0, "medium": 1, "low": 2}

# Categories that describe the same underlying defect from different lenses.
CATEGORY_ALIASES = {
    "missing-input-validation": "input-validation",
    "type-confusion": "input-validation",
    "missing-bounds-check": "input-validation",
    "missing-authn": "access-control",
    "missing-authz": "access-control",
    "idor": "access-control",
    "tenancy-leak": "access-control",
    "privilege-escalation": "access-control",
    "race-condition": "concurrency",
    "toctou": "concurrency",
    "non-atomic-update": "concurrency",
}


def _family(category: str) -> str:
    return CATEGORY_ALIASES.get(category, category)


def fingerprint(rel: str, family: str, start: int, end: int) -> str:
    h = hashlib.sha1(f"{rel}|{family}|{start}|{end}".encode(), usedforsecurity=False).hexdigest()
    return h[:16]


def merge_findings(rows: Iterable[dict]) -> list[dict]:
    """rows: sqlite Rows (or dicts) of raw findings. Returns merged findings."""
    items = [dict(r) for r in rows]
    for it in items:
        it["family"] = _family(it.get("category") or "")

    by_group: dict[tuple, list[dict]] = {}
    for it in items:
        by_group.setdefault((it["rel"], it["family"]), []).append(it)

    merged: list[dict] = []
    for (rel, family), group in by_group.items():
        group.sort(key=lambda x: (x["start_line"] or 0, x["end_line"] or 0))

        clusters: list[list[dict]] = []
        for it in group:
            placed = False
            for cl in clusters:
                lo = min(c["start_line"] for c in cl)
                hi = max(c["end_line"] for c in cl)
                if it["start_line"] <= hi + PROXIMITY and it["end_line"] >= lo - PROXIMITY:
                    cl.append(it)
                    placed = True
                    break
            if not placed:
                clusters.append([it])

        for cl in clusters:
            merged.append(_collapse(rel, family, cl))

    _annotate_colocation(merged, items)

    merged.sort(key=lambda f: (SEV_RANK.get(f["severity"], 9),
                               -f["corroboration"], f["rel"], f["start_line"]))
    return merged


def _annotate_colocation(merged: list[dict], items: list[dict]) -> None:
    """Count passes that flagged *anything* overlapping each finding's range.

    Different lenses describe the same underlying defect in different words
    ("SQL injection" from the injection lens, "unsanitized id" from the logic
    lens). Merging them outright would be wrong -- two genuinely distinct
    defects can share lines, and they need different fixes. So the clusters
    stay separate, but each records how many independent passes flagged
    something at those lines. That is the corroboration signal, and it is what
    triage should sort on.
    """
    by_file: dict[str, list[dict]] = {}
    for it in items:
        by_file.setdefault(it["rel"], []).append(it)

    for f in merged:
        overlapping = [
            it for it in by_file.get(f["rel"], [])
            if it["start_line"] <= f["end_line"] + PROXIMITY
            and it["end_line"] >= f["start_line"] - PROXIMITY
        ]
        voters = {(it["lens"], it["repeat_idx"]) for it in overlapping}
        f["corroboration"] = len(voters)
        f["corroborating_lenses"] = sorted({it["lens"] for it in overlapping})
        # Distinct defect classes reported at these lines, for context.
        f["colocated_families"] = sorted(
            {_family(it.get("category") or "") for it in overlapping}
            - {f["family"]})


def _collapse(rel: str, family: str, cl: list[dict]) -> dict:
    lo = min(c["start_line"] for c in cl)
    hi = max(c["end_line"] for c in cl)

    # Independent passes = distinct (lens, repeat) pairs, not raw row count.
    # Two chunks overlapping the same lines in one pass is not agreement.
    voters = {(c["lens"], c["repeat_idx"]) for c in cl}

    best = min(cl, key=lambda c: (SEV_RANK.get(c["severity"], 9),
                                  CONF_RANK.get(c["confidence"], 9),
                                  -len(c.get("explanation") or "")))
    severity = min((c["severity"] for c in cl),
                   key=lambda s: SEV_RANK.get(s, 9))
    confidence = min((c["confidence"] for c in cl),
                     key=lambda s: CONF_RANK.get(s, 9))

    def _longest(key: str) -> str | None:
        vals = [c.get(key) for c in cl if c.get(key)]
        return max(vals, key=len) if vals else None

    return {
        "fingerprint": fingerprint(rel, family, lo, hi),
        # Which model(s) actually produced this finding. On a resumed scan
        # these can differ from finding to finding, so it belongs here rather
        # than in the report header.
        "models": sorted({c["served_model"] for c in cl if c.get("served_model")}),
        "rel": rel,
        "family": family,
        "category": best["category"],
        "categories": sorted({c["category"] for c in cl}),
        "severity": severity,
        "confidence": confidence,
        "start_line": lo,
        "end_line": hi,
        "symbol": best.get("symbol"),
        "title": best["title"],
        "explanation": _longest("explanation"),
        "trigger": _longest("trigger"),
        "assumptions": _longest("assumptions"),
        "suggested_fix": _longest("fix"),
        "suggested_test": _longest("test"),
        "agreement": len(voters),
        "lenses": sorted({c["lens"] for c in cl}),
        "occurrences": len(cl),
        "variants": [c["title"] for c in cl],
    }


def priority_score(f: dict) -> float:
    """Ordering for triage: severity dominates, agreement and confidence adjust."""
    base = {"critical": 100.0, "high": 70.0, "medium": 40.0, "low": 15.0}
    score = base.get(f["severity"], 30.0)
    score += min(f["agreement"] - 1, 4) * 6.0
    score += min(f.get("corroboration", 1) - f["agreement"], 3) * 3.0
    score += {"high": 8.0, "medium": 0.0, "low": -10.0}.get(f["confidence"], 0.0)
    verdict = f.get("verdict")
    if verdict == "confirmed":
        score += 15.0
    elif verdict == "rejected":
        score -= 60.0
    return score
