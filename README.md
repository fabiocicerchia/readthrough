# codescan

Multi-pass LLM code audit with resumable state and explicit coverage accounting.

Built for the case where you have many repositories and need to know not just
what was found, but what was actually looked at.

## What it does

For every source file it runs several **independent focused passes** rather
than one general "find bugs" prompt, then merges the results.

- **Lenses, not repetition.** Each pass looks for one class of defect
  (injection, access control, invariants, error handling, concurrency,
  secrets, data boundaries). An undirected review drifts toward whatever is
  most obvious in the file and misses entire categories; a narrow one does
  not. `--repeat N` additionally reruns each lens to counter sampling
  variance.
- **Overlapping windows.** Large files are split with overlap so a defect
  spanning a chunk boundary is not invisible to both chunks.
- **Nothing silently dropped.** Every discovered file gets a recorded status.
  Skipped files appear in the report with the reason. Failed API calls are
  recorded as failed tasks and the report names the files they left
  unreviewed. A clean report and an empty report are distinguishable.
- **Resumable.** State lives in SQLite keyed by file content hash. Interrupt
  it, rerun it, and it continues from where it stopped without re-spending on
  completed work. Edit a file and only that file is rescanned.
- **Deduplicated with agreement scoring.** Findings that overlap across passes
  are merged, and the report shows how many independent passes agreed.
  Agreement is the best available triage signal.
- **Optional verification pass.** A second-opinion call re-examines each
  high-severity finding and rejects the ones the code already prevents. This
  is where most of the false-positive reduction comes from.

## Install

```bash
pip install -r requirements.txt      # or: pip install -e .
export ANTHROPIC_API_KEY=sk-ant-...
```

## Use

```bash
# Try the whole pipeline for free first — no API calls, deterministic stub.
python -m codescan scan ./my-repo --fake --out /tmp/dry-run

# See what a real run would cost before committing to it.
python -m codescan scan ./my-repo --estimate-only

# A real scan.
python -m codescan scan ./my-repo --out reports/my-repo

# Tier-1 repo: strongest model, extended thinking, all lenses, verification.
python -m codescan scan ./payments \
  --model claude-opus-5 --thinking 6000 \
  --lenses injection,authz,secrets,logic,errors,concurrency,data \
  --repeat 2 --verify --out reports/payments

# All 80 repos, plus a rollup ranking them by risk.
python -m codescan multi ~/src --out reports/

# Rebuild reports from an existing scan without re-scanning.
python -m codescan report reports/my-repo

python -m codescan lenses     # list available lenses
```

`multi` takes either a directory of repos or a text file of paths, one per
line.

## Output

Written to the output directory:

| File | Purpose |
|---|---|
| `report.md` | Human-readable: coverage first, then findings by priority |
| `findings.json` | Everything, for scripting |
| `coverage.json` | What was scanned, skipped, and failed |
| `findings.sarif` | Upload to GitHub code scanning |
| `scan.db` | Resumable state — keep it, delete it to start fresh |

`multi` additionally writes `rollup.md` and `rollup.json` ranking every repo.

## Cost control

Cost scales with `lines x lenses x repeats`. Levers, roughly in order of
usefulness:

- `--lenses` — the biggest lever. Four default lenses, seven available.
- `--limit N` — only the N largest files. Good for a first look.
- `--ext py,ts` — restrict to the languages that matter.
- `--exclude 'tests/*' --exclude '*_test.go'` — repeatable glob.
- `--model claude-haiku-4-5-20251001` for low-tier repos.
- `--estimate-only` prints projected token counts without calling anything.

Run `--estimate-only` on your largest repo before turning this loose on 80.

## Fitting it to 80 repositories

Do not run the deep configuration everywhere. Rank first, then spend:

1. **Tier 1** (internet-facing, handles auth/money/PII) — all lenses,
   `--repeat 2`, `--verify`, Opus. Perhaps 5-10 repos.
2. **Tier 2** — default lenses, Sonnet, no repeats.
3. **Tier 3** (internal tools) — `--lenses injection,authz --limit 40`, or skip
   entirely and rely on CI static analysis.

Then close the loop: every confirmed finding becomes a Semgrep rule in a
shared ruleset all 80 repos consume. That is the part that compounds. This
tool finds instances; the rules stop the class from recurring. The report's
"recurring defect classes" table is there to tell you which classes are worth
writing a rule for.

## CI

`.github/workflows/codescan.yml` in this repo scans only the files changed in
a pull request and uploads SARIF, so findings appear as inline PR annotations.
Per-PR review is the highest-value placement — small scope, and the author
still has the code in their head.

## What this does not do

Worth being clear, because the failure mode of a tool like this is trusting it
more than it deserves.

- **It does not find everything.** LLM review is sampling. More passes raise
  recall but never to 100%. Treat a clean report as "these passes found
  nothing", not "this code is fine".
- **It cannot execute your code.** Anything depending on runtime state,
  timing, real data, or actual configuration is largely invisible. Fuzzing,
  property-based tests and integration tests find defects this structurally
  cannot.
- **It sees one file at a time.** Defects that only exist in the interaction
  between modules will mostly be missed. The `assumptions` field on each
  finding tells you when the model was reasoning about code it could not see.
- **It produces false positives.** `--verify` cuts them substantially but not
  to zero. Sort by severity and agreement, and read the code before acting.
- **It is not a replacement for Semgrep, CodeQL, dependency scanning, or
  secret scanning.** Those are deterministic, free, and catch the boring
  majority. Get them into CI across all 80 repos first. This tool is for the
  reasoning-dependent defects they cannot express.
