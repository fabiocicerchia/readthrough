# Usage

Day-to-day use once it's installed and configured. For first-time setup see
[Getting Started](getting-started.md).

## Basic usage

```sh
readthrough scan ./my-repo --out reports/my-repo
```

## Lenses

Each pass looks for **one** class of defect. An undirected review drifts toward
whatever is most obvious in the file and misses entire categories; a narrow one
does not.

| Lens | Looks for | Default |
|---|---|:---:|
| `injection` | Untrusted input and injection | ✅ |
| `authz` | Authentication, authorization and tenancy | ✅ |
| `logic` | Invariants and business logic | ✅ |
| `errors` | Error handling, resources and failure modes | ✅ |
| `secrets` | Secrets, crypto and configuration | |
| `concurrency` | Concurrency and shared state | |
| `data` | Data handling, boundaries and types | |

```sh
readthrough lenses                                    # the catalogue, live
readthrough scan ./svc --lenses injection,authz       # only what matters here
```

`--repeat N` reruns each lens N times. That counters sampling variance rather
than adding coverage — a second `injection` pass sometimes surfaces what the
first missed, but a first `secrets` pass surfaces a category no amount of
`injection` repeats ever will. Widen the lens set before raising the repeats.

## Common tasks

=== "Dry-run the pipeline, free"

    ```sh
    readthrough scan ./my-repo --fake --out /tmp/dry-run
    ```

=== "Deep audit of a critical repo"

    ```sh
    readthrough scan ./payments \
      --model claude-opus-5 --thinking 6000 \
      --lenses injection,authz,secrets,logic,errors,concurrency,data \
      --repeat 2 --verify --out reports/payments
    ```

=== "A whole fleet, ranked by risk"

    ```sh
    readthrough multi ~/src --out reports/
    ```

    `multi` takes either a directory of repositories or a text file of paths,
    one per line, and additionally writes `rollup.md` / `rollup.json` ranking
    every repo by severity count.

=== "Rebuild reports without re-scanning"

    ```sh
    readthrough report reports/my-repo
    readthrough report reports/my-repo --stdout | less
    ```

## Verification

```sh
readthrough scan ./my-repo --verify --verify-min-severity high
```

A second-opinion call re-examines each finding at or above the given severity
and rejects the ones the code already prevents. This is where most of the
false-positive reduction comes from. Rejected findings stay in
`findings.json` with `verdict: rejected`, so nothing is silently discarded.

## Reading the report

`report.md` leads with coverage, not findings — deliberately. Before the first
finding you can see how many files were eligible, how many were scanned, how
many passes failed, and which files those failures left unreviewed.

Findings are ordered by priority, which blends severity with **agreement**: how
many independent passes flagged the same thing. Agreement is the best available
triage signal, so start at the top and stop when the signal thins out.

## Fitting it to a fleet

Do not run the deep configuration everywhere. Rank first, then spend:

1. **Tier 1** — internet-facing, handles auth, money or PII. All lenses,
   `--repeat 2`, `--verify`, the strongest model. Typically a handful of repos.
2. **Tier 2** — default lenses, a mid-tier model, no repeats.
3. **Tier 3** — internal tools. `--lenses injection,authz --limit 40`, or skip
   entirely and rely on the static analysis already in CI.

Then close the loop: every confirmed finding becomes a static-analysis rule in
a shared ruleset every repository consumes. That is the part that compounds.
This tool finds instances; the rules stop the class from recurring. The
report's recurring-defect-classes table exists to tell you which classes are
worth a rule.

## Examples

A ready-to-copy pull-request review workflow lives in
[`examples/`](https://github.com/fabiocicerchia/readthrough/tree/main/examples).

## Troubleshooting

??? question "`ANTHROPIC_API_KEY is not set (use --fake to dry-run)`"

    Every command except `--fake`, `--estimate-only`, `report` and `lenses`
    needs the key. Export it, or put it in `.env`.

??? question "The run stops with failed passes"

    Failed passes are recorded, not dropped. The report names the files they
    left unreviewed. Re-run the identical command: completed passes are cached
    by content hash, so only the failures are retried.

??? question "It is costing more than expected"

    Cost scales with `lines × lenses × repeats`. Cut the lens set first, then
    use `--limit` and `--ext`. `--estimate-only` prices a configuration before
    you commit to it. See [Configuration](configuration.md).

??? question "Findings look plausible but wrong"

    Expected — this is sampling, not proof. Turn on `--verify`, then sort by
    severity and agreement and read the code before acting. The `assumptions`
    field on each finding tells you when the model was reasoning about code it
    could not see.
