"""Command line interface and the scan orchestrator."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import FrameType

    from .store import Store

import argparse
import json
import os
import signal
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from . import console
from .discover import chunk_file, discover_files, read_span
from .engine import Engine, PermanentError
from .lenses import DEFAULT_LENSES, LENSES
from .merge import merge_findings, priority_score
from .report import build_results, render_markdown, write_reports
from .store import Store

DEFAULT_MODEL = "claude-sonnet-5"

_stop = threading.Event()


def _install_sigint() -> None:
    def handler(signum: int, frame: FrameType | None) -> None:
        if _stop.is_set():
            console.err("\nforced exit")
            os._exit(130)
        _stop.set()
        console.err(
            "\nstopping after in-flight passes finish; progress is saved, "
            "re-run the same command to resume (Ctrl-C again to force)"
        )
    signal.signal(signal.SIGINT, handler)


def task_key(sha: str, lens: str, chunk_idx: int, repeat_idx: int) -> str:
    return f"{sha[:16]}:{lens}:{chunk_idx}:{repeat_idx}"


class Progress:
    def __init__(self, total: int, quiet: bool = False):
        self.total, self.done, self.failed, self.findings = total, 0, 0, 0
        self.quiet = quiet
        self.lock = threading.Lock()
        self.t0 = time.time()

    def tick(self, ok: bool, n_findings: int = 0) -> None:
        with self.lock:
            self.done += 1
            if not ok:
                self.failed += 1
            self.findings += n_findings
            if self.quiet:
                return
            elapsed = time.time() - self.t0
            rate = self.done / elapsed if elapsed > 0 else 0
            eta = (self.total - self.done) / rate if rate > 0 else 0
            sys.stderr.write(
                f"\r  {self.done}/{self.total} passes · "
                f"{self.findings} raw findings · {self.failed} failed · "
                f"eta {int(eta // 60)}m{int(eta % 60):02d}s   ")
            sys.stderr.flush()

    def finish(self) -> None:
        if not self.quiet:
            sys.stderr.write("\n")


def cmd_scan(args: argparse.Namespace) -> int:  # noqa: PLR0912,PLR0915 — the scan pipeline, in the order it runs
    root = Path(args.path).resolve()
    if not root.is_dir():
        console.err(f"not a directory: {root}")
        return 2

    outdir = Path(args.out) if args.out else Path("readthrough-reports") / root.name
    outdir.mkdir(parents=True, exist_ok=True)

    lens_ids = [x.strip() for x in args.lenses.split(",") if x.strip()]
    unknown = [x for x in lens_ids if x not in LENSES]
    if unknown:
        console.err(
            f"unknown lenses: {', '.join(unknown)}\navailable: {', '.join(LENSES)}"
        )
        return 2

    if not args.fake and not os.environ.get("ANTHROPIC_API_KEY"):
        console.err("ANTHROPIC_API_KEY is not set (use --fake to dry-run)")
        return 2

    store = Store(outdir / "scan.db")
    store.set_meta("root", str(root))
    store.set_meta("model", args.model)
    store.set_meta("lenses", lens_ids)
    store.set_meta("repeats", args.repeat)
    store.set_meta("verified", bool(args.verify))
    if not store.get_meta("started_at"):
        store.set_meta("started_at",
                       datetime.now(timezone.utc).isoformat(timespec="seconds"))

    console.out(f"scanning {root}")
    include = ({e if e.startswith(".") else "." + e
                for e in args.ext.split(",")} if args.ext else None)
    files = discover_files(root, max_bytes=args.max_file_bytes,
                           include_exts=include,
                           exclude_globs=tuple(args.exclude or ()),
                           min_loc=args.min_loc)
    store.upsert_files(files)

    eligible = [f for f in files if f.status == "pending"]
    skipped = len(files) - len(eligible)
    console.out(f"  {len(eligible)} files eligible, {skipped} skipped, "
          f"{sum(f.loc for f in eligible):,} lines")

    if args.limit:
        eligible.sort(key=lambda f: -f.loc)
        eligible = eligible[:args.limit]
        console.out(f"  --limit: reviewing the {len(eligible)} largest")

    # Build the task list, dropping anything already completed.
    completed = set() if args.force else store.completed_keys()
    tasks = []
    total_planned = 0
    for info in eligible:
        for chunk in chunk_file(info, args.chunk_lines, args.overlap):
            for lens in lens_ids:
                for rep in range(args.repeat):
                    total_planned += 1
                    key = task_key(info.sha256, lens, chunk.chunk_idx, rep)
                    if key in completed:
                        continue
                    tasks.append((key, info, chunk, lens, rep))

    resumed = total_planned - len(tasks)
    if resumed > 0:
        console.out(f"  resuming: {resumed} passes already complete")
    console.out(f"  {len(tasks)} passes to run "
          f"({len(lens_ids)} lenses x {args.repeat} repeat(s))")

    if not tasks:
        console.out("  nothing to do")
    else:
        if args.estimate_only:
            est_in = sum(len(c.numbered) // 3.5 + 1500
                         for _, _, c, _, _ in tasks)
            console.out(f"\nestimate: ~{int(est_in):,} input tokens, "
                  f"~{len(tasks) * 500:,} output tokens")
            store.close()
            return 0

        engine = Engine(args.model, max_tokens=args.max_tokens,
                        thinking_budget=args.thinking, fake=args.fake,
                        temperature=args.temperature)
        _install_sigint()
        prog = Progress(len(tasks), quiet=args.quiet)

        def run(t: tuple) -> None:
            key, info, chunk, lens, rep = t
            if _stop.is_set():
                return None
            t0 = time.time()
            attempts = store.prior_attempts(key) + 1
            err, findings, usage = None, [], None
            try:
                findings, usage = engine.scan_chunk(chunk, lens)
                status = "done"
            except PermanentError as exc:
                status, err = "failed", f"permanent: {exc}"
            except Exception as exc:  # transport exhausted, unexpected
                status, err = "failed", f"{type(exc).__name__}: {exc}"
            store.record_task(
                key=key, rel=info.rel, sha256=info.sha256, lens=lens,
                chunk_idx=chunk.chunk_idx, repeat_idx=rep,
                start_line=chunk.start_line, end_line=chunk.end_line,
                status=status, attempts=attempts, error=err,
                in_tokens=usage.in_tokens if usage else 0,
                out_tokens=usage.out_tokens if usage else 0,
                duration_ms=int((time.time() - t0) * 1000),
                findings=findings, served_model=engine.last_served)
            prog.tick(status == "done", len(findings))
            return status

        console.out()
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futs = [pool.submit(run, t) for t in tasks]
            for fut in as_completed(futs):
                fut.result()
        prog.finish()

        # What answered, as opposed to what was asked for. Accumulate across
        # resumed runs so a report built from an old scan.db keeps naming
        # every model that contributed to it.
        if engine.served_models:
            prior = set(store.get_meta("served_models", []))
            store.set_meta("served_models",
                           sorted(prior | engine.served_models))

    # -- verification pass ------------------------------------------------
    if args.verify and not _stop.is_set():
        _verify(store, args, lens_ids)

    res = build_results(store)
    paths = write_reports(res, outdir)
    store.close()

    _summarise(res, paths)
    return 0


def _verify(store: Store, args: argparse.Namespace, lens_ids: list[str]) -> None:
    merged = merge_findings(store.raw_findings())
    have = store.verdicts()
    floor = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    cutoff = floor.get(args.verify_min_severity, 1)
    todo = [f for f in merged
            if floor.get(f["severity"], 9) <= cutoff
            and f["fingerprint"] not in have]
    if not todo:
        return

    console.out(f"\nverifying {len(todo)} findings "
          f"(severity >= {args.verify_min_severity})")
    engine = Engine(args.model, max_tokens=2000, fake=args.fake)
    prog = Progress(len(todo), quiet=args.quiet)

    def check(f: dict) -> None:
        if _stop.is_set():
            return
        code = read_span(store.abspath(f["rel"]), f["start_line"], f["end_line"])
        if not code:
            return
        try:
            v, usage = engine.verify(f, code)
            store.set_verdict(f["fingerprint"], v["verdict"], v["reasoning"],
                              v["severity"], usage.in_tokens, usage.out_tokens)
            prog.tick(True)
        except Exception as exc:
            store.set_verdict(f["fingerprint"], "uncertain",
                              f"verification failed: {exc}", f["severity"])
            prog.tick(False)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(as_completed([pool.submit(check, f) for f in todo]))
    prog.finish()


def _summarise(res: dict, paths: dict) -> None:
    cov = res["coverage"]
    active = [f for f in res["findings"] if f.get("verdict") != "rejected"]
    sev = {s: sum(1 for f in active if f["severity"] == s)
           for s in ("critical", "high", "medium", "low")}
    console.out()
    console.out(f"  coverage : {cov['files_scanned']}/{cov['files_eligible']} files, "
          f"{cov['tasks_done']}/{cov['tasks_total']} passes")
    if cov["tasks_failed"]:
        console.out(f"  FAILED   : {cov['tasks_failed']} passes "
              f"({len(cov['files_uncovered'])} files left unreviewed) "
              f"-- re-run to retry")
    console.out(f"  findings : {sev['critical']} critical, {sev['high']} high, "
          f"{sev['medium']} medium, {sev['low']} low")
    console.out(f"  tokens   : {res['usage']['input_tokens']:,} in / "
          f"{res['usage']['output_tokens']:,} out")
    console.out(f"  report   : {paths['markdown']}")


def cmd_report(args: argparse.Namespace) -> int:
    db = Path(args.dir) / "scan.db"
    if not db.exists():
        console.err(f"no scan.db in {args.dir}")
        return 2
    store = Store(db)
    res = build_results(store)
    store.close()
    if args.stdout:
        console.out(render_markdown(res))
    else:
        paths = write_reports(res, Path(args.dir))
        _summarise(res, paths)
    return 0


def cmd_multi(args: argparse.Namespace) -> int:
    """Scan many repositories and write a rollup index."""
    listing = Path(args.list)
    if listing.is_dir():
        repos = sorted(p for p in listing.iterdir()
                       if p.is_dir() and not p.name.startswith("."))
    else:
        repos = [Path(line.strip()).resolve()
                 for line in listing.read_text().splitlines()
                 if line.strip() and not line.startswith("#")]

    outroot = Path(args.out)
    outroot.mkdir(parents=True, exist_ok=True)
    rollup = []

    for i, repo in enumerate(repos, 1):
        console.out(f"\n=== [{i}/{len(repos)}] {repo.name} " + "=" * 30)
        if not repo.is_dir():
            console.out(f"  skipping, not a directory: {repo}")
            rollup.append({"repo": str(repo), "error": "not a directory"})
            continue
        sub = argparse.Namespace(**vars(args))
        sub.path = str(repo)
        sub.out = str(outroot / repo.name)
        try:
            cmd_scan(sub)
            data = json.loads((outroot / repo.name / "findings.json").read_text())
            active = [f for f in data["findings"] if f.get("verdict") != "rejected"]
            rollup.append({
                "repo": repo.name,
                "path": str(repo),
                "files_scanned": data["coverage"]["files_scanned"],
                "files_eligible": data["coverage"]["files_eligible"],
                "tasks_failed": data["coverage"]["tasks_failed"],
                "critical": sum(1 for f in active if f["severity"] == "critical"),
                "high": sum(1 for f in active if f["severity"] == "high"),
                "medium": sum(1 for f in active if f["severity"] == "medium"),
                "low": sum(1 for f in active if f["severity"] == "low"),
                "top": [{"title": f["title"], "file": f["rel"],
                         "line": f["start_line"], "severity": f["severity"]}
                        for f in sorted(active, key=lambda x: -priority_score(x))[:5]],
                "report": str(outroot / repo.name / "report.md"),
            })
        except Exception as exc:
            console.err(f"  repo failed: {exc}")
            rollup.append({"repo": repo.name, "error": str(exc)})
        if _stop.is_set():
            console.out("stopping; remaining repos not scanned")
            break

    rollup.sort(key=lambda r: (-(r.get("critical", 0) * 10 + r.get("high", 0))))
    (outroot / "rollup.json").write_text(json.dumps(rollup, indent=2))

    lines = ["# Fleet audit rollup", "",
             f"{len(rollup)} repositories · "
             f"{datetime.now(timezone.utc).isoformat(timespec='seconds')}", "",
             "| Repo | Coverage | Critical | High | Medium | Low | Failed passes |",
             "|---|---|---|---|---|---|---|"]
    for r in rollup:
        if "error" in r:
            lines.append(f"| `{r['repo']}` | — | — | — | — | — | {r['error']} |")
            continue
        lines.append(
            f"| [`{r['repo']}`]({r['repo']}/report.md) | "
            f"{r['files_scanned']}/{r['files_eligible']} | {r['critical']} | "
            f"{r['high']} | {r['medium']} | {r['low']} | {r['tasks_failed']} |")
    lines += ["", "## Highest priority findings across the fleet", ""]
    for r in rollup:
        if r.get("top"):
            lines.append(f"### {r['repo']}")
            lines.append("")
            for t in r["top"]:
                lines.append(f"- **{t['severity'].upper()}** "
                             f"`{t['file']}:{t['line']}` — {t['title']}")
            lines.append("")
    (outroot / "rollup.md").write_text("\n".join(lines), encoding="utf-8")
    console.out(f"\nrollup: {outroot / 'rollup.md'}")
    return 0


def cmd_lenses(args: argparse.Namespace) -> int:
    for lid, lens in LENSES.items():
        mark = "*" if lid in DEFAULT_LENSES else " "
        console.out(f"{mark} {lid:<12} {lens.title}")
    console.out("\n* = enabled by default")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="readthrough",
        description="Multi-pass LLM code audit with resumable state and "
                    "explicit coverage accounting.")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--out", "-o", help="output directory")
        sp.add_argument("--model", default=os.environ.get("READTHROUGH_MODEL",
                                                          DEFAULT_MODEL))
        sp.add_argument("--lenses", default=",".join(DEFAULT_LENSES),
                        help="comma separated; see `readthrough lenses`")
        sp.add_argument("--repeat", type=int, default=1,
                        help="identical repeats per lens, to counter sampling "
                             "variance (default 1)")
        sp.add_argument("--workers", "-j", type=int, default=6)
        sp.add_argument("--chunk-lines", type=int, default=350)
        sp.add_argument("--overlap", type=int, default=60)
        sp.add_argument("--max-tokens", type=int, default=8000)
        sp.add_argument("--thinking", type=int, default=None,
                        metavar="BUDGET",
                        help="enable extended thinking with this token budget")
        sp.add_argument("--temperature", type=float, default=None)
        sp.add_argument("--max-file-bytes", type=int, default=400_000)
        sp.add_argument("--min-loc", type=int, default=3)
        sp.add_argument("--ext", help="restrict to these extensions, e.g. py,ts")
        sp.add_argument("--exclude", action="append",
                        help="glob to exclude; repeatable")
        sp.add_argument("--limit", type=int,
                        help="only the N largest eligible files")
        sp.add_argument("--verify", action="store_true",
                        help="second-opinion pass over merged findings")
        sp.add_argument("--verify-min-severity", default="high",
                        choices=["critical", "high", "medium", "low"])
        sp.add_argument("--force", action="store_true",
                        help="ignore cached results and redo every pass")
        sp.add_argument("--fake", action="store_true",
                        help="offline stub; exercises the pipeline for free")
        sp.add_argument("--estimate-only", action="store_true")
        sp.add_argument("--quiet", "-q", action="store_true")

    sp = sub.add_parser("scan", help="scan one repository")
    sp.add_argument("path")
    common(sp)
    sp.set_defaults(func=cmd_scan)

    sp = sub.add_parser("multi", help="scan many repositories")
    sp.add_argument("list", help="file of paths, or a directory of repos")
    common(sp)
    sp.set_defaults(func=cmd_multi)

    sp = sub.add_parser("report", help="rebuild reports from an existing scan.db")
    sp.add_argument("dir")
    sp.add_argument("--stdout", action="store_true")
    sp.set_defaults(func=cmd_report)

    sp = sub.add_parser("lenses", help="list available lenses")
    sp.set_defaults(func=cmd_lenses)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "out", None) is None and args.cmd == "multi":
        args.out = "readthrough-reports"
    try:
        return args.func(args)
    except BrokenPipeError:
        # Output was piped into something that closed early (`| head`).
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 0
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
