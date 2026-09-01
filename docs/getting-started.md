# Getting Started

## Prerequisites

- Python 3.10 or newer.
- An Anthropic API key, for anything other than a `--fake` run.

## Install

```sh
curl -fsSL https://raw.githubusercontent.com/fabiocicerchia/readthrough/main/install.sh | sh
```

The installer prefers `pipx` (isolated virtualenv, `readthrough` on `PATH`) and
falls back to `pip install --user`. To install a specific tag instead of `main`,
set `READTHROUGH_REF`:

```sh
curl -fsSL https://raw.githubusercontent.com/fabiocicerchia/readthrough/main/install.sh | READTHROUGH_REF=v1.0.0 sh
```

=== "pipx"

    ```sh
    pipx install git+https://github.com/fabiocicerchia/readthrough.git
    ```

=== "pip"

    ```sh
    pip install --user git+https://github.com/fabiocicerchia/readthrough.git
    ```

=== "From a clone"

    ```sh
    git clone https://github.com/fabiocicerchia/readthrough.git
    cd readthrough
    make setup     # editable install + dev extras + pre-commit hook
    make install   # or: put it on your PATH without the dev tooling
    ```

## Configure

```sh
export ANTHROPIC_API_KEY=sk-ant-...
```

Read from the process environment only — there is no dotenv loading. See
[Configuration](configuration.md) for the full list.

## Your first run — free

`--fake` swaps the API client for a deterministic offline stub. It exercises
discovery, chunking, every pass, the merge and the whole report set without a
single API call, so you can see the shape of the output before spending
anything.

```sh
readthrough scan ./my-repo --fake --out /tmp/dry-run
cat /tmp/dry-run/report.md
```

## Estimate before you spend

```sh
readthrough scan ./my-repo --estimate-only
```

This prints projected input and output token counts for the passes it would
run, and writes nothing. Run it against your largest repository before turning
the tool loose on a fleet.

## A real scan

```sh
readthrough scan ./my-repo --out reports/my-repo
```

Interrupt it with Ctrl-C at any point: in-flight passes finish, state is
committed, and re-running the identical command resumes rather than
re-spending. State is keyed by file content hash, so editing one file rescans
only that file.

## Next

- [Usage](usage.md) — lenses, repeats, verification, scanning a fleet.
- [Configuration](configuration.md) — every flag, and what drives cost.
- [API Reference](api.md) — the full CLI surface and the output formats.
