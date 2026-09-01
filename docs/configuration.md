# Configuration

Everything is a command-line flag; there is no config file.

## Environment variables

Read from the process environment only — there is no dotenv loading, so a
`.env` file in the working directory has no effect. Export them, or use your
shell's own env loader.

| Variable | Default | Description |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | — | Required for any real scan. `--fake` and `--estimate-only` do not need it. |
| `READTHROUGH_MODEL` | `claude-sonnet-5` | Default model. `--model` overrides it per run. |

Precedence, highest first: command-line flags → environment → built-in
defaults.

!!! tip
    Never commit the key. In CI, pass it as a secret at run time; locally, keep
    it in your shell profile or a secret manager. CI runs gitleaks over the
    tree either way.

## Selecting what gets scanned

| Flag | Default | Effect |
| --- | --- | --- |
| `--ext py,ts` | all known | Restrict to these extensions. |
| `--exclude GLOB` | — | Repeatable. `--exclude 'tests/*' --exclude '*_test.go'`. |
| `--limit N` | — | Only the N largest eligible files. |
| `--min-loc N` | `3` | Skip files shorter than this. |
| `--max-file-bytes N` | `400000` | Skip files larger than this. |

Skipped files are not silently dropped — each one appears in the report with
its reason.

## Passes

| Flag | Default | Effect |
| --- | --- | --- |
| `--lenses a,b,c` | `injection,authz,logic,errors` | Which defect classes to look for. |
| `--repeat N` | `1` | Identical reruns per lens, to counter sampling variance. |
| `--chunk-lines N` | `350` | Window size for splitting large files. |
| `--overlap N` | `60` | Overlap between windows, so a defect on a boundary is not invisible to both. |
| `--workers N` | `6` | Concurrent passes. |

## Model

| Flag | Default | Effect |
| --- | --- | --- |
| `--model ID` | `$READTHROUGH_MODEL` or `claude-sonnet-5` | Model to call. |
| `--thinking N` | off | Enable extended thinking with an N-token budget. |
| `--max-tokens N` | `8000` | Output cap per pass. |
| `--temperature F` | model default | Rarely worth changing. |

## Verification

| Flag | Default | Effect |
| --- | --- | --- |
| `--verify` | off | Second-opinion pass over merged findings. |
| `--verify-min-severity` | `high` | Floor for what gets verified: `critical`, `high`, `medium`, `low`. |

## Run control

| Flag | Default | Effect |
| --- | --- | --- |
| `--out DIR` | `readthrough-reports/<repo>` | Where reports and `scan.db` go. |
| `--force` | off | Ignore cached results and redo every pass. |
| `--fake` | off | Offline deterministic stub; no API calls, no cost. |
| `--estimate-only` | off | Print projected token counts and exit without writing reports. |
| `--quiet` / `-q` | off | Suppress the progress line. |

## What drives cost

Cost scales with **lines × lenses × repeats**. The levers, in order of
usefulness:

1. `--lenses` — the biggest one. Four of seven are on by default; every lens
   you add is another full pass over every file.
2. `--limit N` — the N largest files usually carry most of the risk.
3. `--ext py,ts` — stop paying to review generated or irrelevant languages.
4. `--exclude` — tests, vendored trees, fixtures.
5. `--model` — a cheaper model for low-tier repositories.

`--estimate-only` prices a configuration without calling anything. Run it
against your largest repository before scanning a fleet.

## Validating your setup

```sh
readthrough scan . --fake --out /tmp/check    # exercises everything, costs nothing
readthrough lenses                            # confirms the install is importable
```
