# readthrough

> Multi-pass LLM code audit with resumable state and explicit coverage accounting.

[![CI](https://github.com/fabiocicerchia/readthrough/actions/workflows/ci.yml/badge.svg)](https://github.com/fabiocicerchia/readthrough/actions/workflows/ci.yml)
[![Code Quality](https://github.com/fabiocicerchia/readthrough/actions/workflows/code-quality.yml/badge.svg)](https://github.com/fabiocicerchia/readthrough/actions/workflows/code-quality.yml)
[![Security](https://github.com/fabiocicerchia/readthrough/actions/workflows/security.yml/badge.svg)](https://github.com/fabiocicerchia/readthrough/actions/workflows/security.yml)
[![License](https://img.shields.io/badge/license-Apache_2.0-blue.svg)](LICENSE)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/fabiocicerchia/readthrough/badge)](https://securityscorecards.dev/viewer/?uri=github.com/fabiocicerchia/readthrough)
[![CI carbon](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/fabiocicerchia/readthrough/gh-pages/badge.json)](.github/workflows/carbon-badge.yml)

Built for the case where you have many repositories and need to know not just
what was found, but what was actually looked at.

For every source file it runs several **independent focused passes** rather
than one general "find bugs" prompt, then merges the results.

## Features

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

```sh
curl -fsSL https://raw.githubusercontent.com/fabiocicerchia/readthrough/main/install.sh | sh
```

Or with pip / pipx:

```sh
pipx install git+https://github.com/fabiocicerchia/readthrough.git
```

Then set the API key:

```sh
export ANTHROPIC_API_KEY=sk-ant-...
```

Python 3.10+. The only runtime dependency is the `anthropic` SDK.

## Usage

```sh
# Try the whole pipeline for free first — no API calls, deterministic stub.
readthrough scan ./my-repo --fake --out /tmp/dry-run

# See what a real run would cost before committing to it.
readthrough scan ./my-repo --estimate-only

# A real scan.
readthrough scan ./my-repo --out reports/my-repo

# Tier-1 repo: strongest model, extended thinking, all lenses, verification.
readthrough scan ./payments \
  --model claude-opus-5 --thinking 6000 \
  --lenses injection,authz,secrets,logic,errors,concurrency,data \
  --repeat 2 --verify --out reports/payments

# All 80 repos, plus a rollup ranking them by risk.
readthrough multi ~/src --out reports/

# Rebuild reports from an existing scan without re-scanning.
readthrough report reports/my-repo

readthrough lenses     # list available lenses
```

`multi` takes either a directory of repos or a text file of paths, one per
line.

### Output

Written to the output directory:

| File | Purpose |
|---|---|
| `report.md` | Human-readable: coverage first, then findings by priority |
| `findings.json` | Everything, for scripting |
| `coverage.json` | What was scanned, skipped, and failed |
| `findings.sarif` | Upload to GitHub code scanning |
| `scan.db` | Resumable state — keep it, delete it to start fresh |

`multi` additionally writes `rollup.md` and `rollup.json` ranking every repo.

### Cost control

Cost scales with `lines x lenses x repeats`. Levers, roughly in order of
usefulness:

- `--lenses` — the biggest lever. Four default lenses, seven available.
- `--limit N` — only the N largest files. Good for a first look.
- `--ext py,ts` — restrict to the languages that matter.
- `--exclude 'tests/*' --exclude '*_test.go'` — repeatable glob.
- `--model claude-haiku-4-5-20251001` for low-tier repos.
- `--estimate-only` prints projected token counts without calling anything.

Run `--estimate-only` on your largest repo before turning this loose on 80.

### Fitting it to a fleet

Do not run the deep configuration everywhere. Rank first, then spend:

1. **Tier 1** (internet-facing, handles auth/money/PII) — all lenses,
   `--repeat 2`, `--verify`, Opus. Perhaps 5-10 repos.
2. **Tier 2** — default lenses, Sonnet, no repeats.
3. **Tier 3** (internal tools) — `--lenses injection,authz --limit 40`, or skip
   entirely and rely on CI static analysis.

Then close the loop: every confirmed finding becomes a Semgrep rule in a
shared ruleset all the repos consume. That is the part that compounds. This
tool finds instances; the rules stop the class from recurring. The report's
"recurring defect classes" table is there to tell you which classes are worth
writing a rule for.

## CI

`.github/workflows/readthrough.yml` scans only the files changed in a pull
request and uploads SARIF, so findings appear as inline PR annotations. Per-PR
review is the highest-value placement — small scope, and the author still has
the code in their head. See
[`examples/github-actions/`](examples/github-actions/) for the version to drop
into another repository.

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
  majority. Get them into CI first. This tool is for the reasoning-dependent
  defects they cannot express.

## Documentation

Full docs live in [`docs/`](docs/). Runnable examples live in
[`examples/`](examples/).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). By participating you agree to the
[Code of Conduct](CODE_OF_CONDUCT.md).

## Security

Found a vulnerability? See [SECURITY.md](SECURITY.md) — please don't open a
public issue.

## License

[Apache 2.0](LICENSE) © 2026 Fabio Cicerchia
