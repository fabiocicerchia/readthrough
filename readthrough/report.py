"""Report generation.

The coverage section comes first and is the point of the whole thing: it says
what was scanned, what was skipped and why, and what failed. A findings list
without that is unfalsifiable -- you cannot tell "clean" from "never looked".
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .merge import merge_findings, priority_score

SEV_LABEL = {"critical": "CRITICAL", "high": "HIGH",
             "medium": "MEDIUM", "low": "LOW"}


def build_results(store) -> dict:
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


def _pct(n, d):
    return f"{(100.0 * n / d):.1f}%" if d else "n/a"


def render_markdown(res: dict, max_detail: int = 250) -> str:
    m, cov, use = res["meta"], res["coverage"], res["usage"]
    findings = res["findings"]
    active = [f for f in findings if f.get("verdict") != "rejected"]
    rejected = [f for f in findings if f.get("verdict") == "rejected"]

    sev_counts = Counter(f["severity"] for f in active)
    # Every model that produced a finding in this scan.db, across all runs that
    # built it. When there is more than one, each finding names its own.
    all_models = sorted({mo for f in findings for mo in (f.get("models") or [])})
    out = []
    A = out.append

    A(f"# Code audit: `{m['root']}`")
    A("")
    A(f"Generated {m['generated_at']} | model `{m['model']}` | "
      f"lenses: {', '.join(m['lenses'])} | repeats: {m['repeats']}"
      + (" | verification pass: on" if m.get("verified") else ""))
    A("")

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
        A(f"> **Requested `{m['model']}`; answered by "
          f"{', '.join(f'`{s}`' for s in served)}.** A proxy may be resolving "
          f"an alias, or falling through to a different model entirely — judge "
          f"the findings against whatever actually answered. Passes cached "
          f"from an earlier run keep the model that answered *them*; each "
          f"finding names its own below.")
        A("")

    # -- coverage ------------------------------------------------------
    A("## Coverage")
    A("")
    A("| | |")
    A("|---|---|")
    A(f"| Files discovered | {cov['files_discovered']} |")
    A(f"| Eligible for review | {cov['files_eligible']} "
      f"({cov['total_loc']:,} lines) |")
    A(f"| Scanned | {cov['files_scanned']} "
      f"({_pct(cov['files_scanned'], cov['files_eligible'])}) |")
    A(f"| Skipped by filter | {cov['files_skipped']} |")
    A(f"| Never started | {cov['files_not_started']} |")
    A(f"| Passes run | {cov['tasks_done']} of {cov['tasks_total']} |")
    A(f"| Passes failed | {cov['tasks_failed']} |")
    A(f"| Tokens | {use['input_tokens']:,} in / {use['output_tokens']:,} out |")
    A("")

    if cov["files_uncovered"]:
        A("> **Gaps.** These files produced no successful pass and are "
          "therefore unreviewed:")
        A("> ")
        for r in cov["files_uncovered"][:60]:
            A(f"> - `{r}`")
        if len(cov["files_uncovered"]) > 60:
            A(f"> - ... and {len(cov['files_uncovered']) - 60} more")
        A("")
    if cov["files_partial"]:
        A(f"> **Partial.** {len(cov['files_partial'])} files had at least one "
          "pass fail; see the appendix. Their results are incomplete.")
        A("")
    if cov["files_not_started"]:
        A(f"> **Not started.** {cov['files_not_started']} eligible files were "
          "never queued (run interrupted?). Re-run the same command to finish.")
        A("")

    # -- summary -------------------------------------------------------
    A("## Findings summary")
    A("")
    if not active:
        A("No findings survived merging and verification.")
        A("")
    else:
        A("| Severity | Count |")
        A("|---|---|")
        for sev in ("critical", "high", "medium", "low"):
            if sev_counts.get(sev):
                A(f"| {SEV_LABEL[sev]} | {sev_counts[sev]} |")
        A(f"| **Total** | **{len(active)}** |")
        A("")
        if rejected:
            A(f"{len(rejected)} additional findings were rejected by the "
              "verification pass and are listed in the appendix.")
            A("")

        by_file = Counter(f["rel"] for f in active)
        A("**Files with the most findings**")
        A("")
        A("| File | Findings |")
        A("|---|---|")
        for rel, n in by_file.most_common(12):
            A(f"| `{rel}` | {n} |")
        A("")

        by_cat = Counter(f["family"] for f in active)
        A("**Recurring defect classes** — these are the candidates for a "
          "Semgrep rule rather than a one-off fix.")
        A("")
        A("| Class | Count |")
        A("|---|---|")
        for cat, n in by_cat.most_common(15):
            A(f"| `{cat}` | {n} |")
        A("")

    # -- detail --------------------------------------------------------
    if active:
        A("## Findings")
        A("")
        for i, f in enumerate(active[:max_detail], 1):
            A(f"### {i}. {SEV_LABEL[f['severity']]} — {f['title']}")
            A("")
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
            A(" · ".join(bits))
            A("")
            A(f["explanation"])
            A("")
            if f.get("trigger"):
                A(f"**Trigger.** {f['trigger']}")
                A("")
            if f.get("assumptions"):
                A(f"**Assumes.** {f['assumptions']}")
                A("")
            if f.get("suggested_fix"):
                A(f"**Fix.** {f['suggested_fix']}")
                A("")
            if f.get("suggested_test"):
                A(f"**Regression test.** {f['suggested_test']}")
                A("")
            if f.get("verdict_reasoning"):
                A(f"**Verification.** {f['verdict_reasoning']}")
                A("")
            if f.get("colocated_families"):
                A("**Also flagged at these lines.** "
                  + ", ".join(f"`{c}`" for c in f["colocated_families"])
                  + " — this range is worth reading in full rather than "
                    "patching one line.")
                A("")
            models = f.get("models") or []
            model_note = (f"model: {', '.join(models)} · "
                          if len(all_models) > 1 and models else "")
            A(f"<sub>found by: {', '.join(f['lenses'])} · {model_note}"
              f"fingerprint `{f['fingerprint']}`</sub>")
            A("")
            A("---")
            A("")
        if len(active) > max_detail:
            A(f"*{len(active) - max_detail} further findings omitted from this "
              "document; all of them are in `findings.json`.*")
            A("")

    # -- appendix ------------------------------------------------------
    A("## Appendix")
    A("")
    if cov["failed_detail"]:
        A("### Failed passes")
        A("")
        A("These passes did not complete. Re-running resumes them.")
        A("")
        A("| File | Lens | Lines | Attempts | Error |")
        A("|---|---|---|---|---|")
        for d in cov["failed_detail"][:100]:
            err = d["error"].replace("|", "\\|").replace("\n", " ")[:120]
            A(f"| `{d['file']}` | {d['lens']} | {d['lines']} | "
              f"{d['attempts']} | {err} |")
        A("")
    else:
        A("### Failed passes")
        A("")
        A("None. Every queued pass completed.")
        A("")

    if rejected:
        A("### Rejected by verification")
        A("")
        A("| File | Lines | Title | Why rejected |")
        A("|---|---|---|---|")
        for f in rejected[:80]:
            why = (f.get("verdict_reasoning") or "").replace("|", "\\|")[:160]
            A(f"| `{f['rel']}` | {f['start_line']}-{f['end_line']} | "
              f"{f['title'][:70]} | {why} |")
        A("")

    if cov["skipped_detail"]:
        A("### Skipped files")
        A("")
        reasons = Counter(d["reason"].split("(")[0].strip()
                          for d in cov["skipped_detail"])
        A("| Reason | Count |")
        A("|---|---|")
        for r, n in reasons.most_common():
            A(f"| {r} | {n} |")
        A("")
        A("<details><summary>Full list</summary>")
        A("")
        for d in cov["skipped_detail"][:400]:
            A(f"- `{d['file']}` — {d['reason']}")
        A("")
        A("</details>")
        A("")

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
