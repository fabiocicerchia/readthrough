# API Reference

The public interface is the `readthrough` command. Every flag is listed in
[Configuration](configuration.md); this page covers the command surface and the
output formats.

## CLI

```text
NAME
    readthrough — multi-pass LLM code audit with resumable state and explicit
    coverage accounting

USAGE
    readthrough scan   <path>  [options]   scan one repository
    readthrough multi  <list>  [options]   scan many; <list> is a directory of
                                        repos or a file of paths, one per line
    readthrough report <dir>   [--stdout]  rebuild reports from an existing scan.db
    readthrough lenses                     list available lenses
```

### Exit status

| Code | Meaning |
| --- | --- |
| `0` | Ran to completion. **Findings do not change the exit code** — gate on `findings.json` instead. |
| `2` | Usage error: bad path, unknown lens, missing API key, no `scan.db` to report on. |
| `130` | Interrupted. Progress is committed; re-run to resume. |

## Output files

Written to `--out`:

| File | Purpose |
|---|---|
| `report.md` | Human-readable: coverage first, then findings by priority |
| `findings.json` | Everything, for scripting |
| `coverage.json` | What was scanned, skipped, and failed |
| `findings.sarif` | SARIF 2.1.0, for GitHub code scanning |
| `scan.db` | Resumable state — keep it; delete it to start fresh |

`multi` additionally writes `rollup.md` and `rollup.json`.

### `findings.json`

```json
{
  "coverage": {
    "files_eligible": 42,
    "files_scanned": 42,
    "files_skipped": 7,
    "tasks_total": 168,
    "tasks_done": 168,
    "tasks_failed": 0,
    "files_uncovered": []
  },
  "usage": { "input_tokens": 0, "output_tokens": 0 },
  "findings": [
    {
      "rel": "app/db.py",
      "start_line": 7,
      "end_line": 9,
      "severity": "high",
      "category": "injection",
      "title": "SQL built by string interpolation",
      "explanation": "...",
      "assumptions": "Assumes user_id reaches this function unvalidated.",
      "agreement": 3,
      "verdict": "confirmed"
    }
  ]
}
```

Two fields carry most of the triage value:

- **`agreement`** — how many independent passes flagged the same thing. The
  best available signal that a finding is real.
- **`assumptions`** — what the model was reasoning about but could not see.
  When this is populated, the finding depends on context outside the file.

`verdict` is present only when `--verify` ran: `confirmed`, `rejected` or
`uncertain`. Rejected findings are kept, not deleted.

### Gating a build

Findings never set the exit code, because "should this fail the build" is a
policy question. Express the policy explicitly:

```sh
python - <<'EOF'
import json, sys
d = json.load(open("reports/my-repo/findings.json"))
n = sum(1 for f in d["findings"]
        if f["severity"] == "critical" and f.get("verdict") != "rejected")
print(f"{n} unrejected critical finding(s)")
sys.exit(1 if n else 0)
EOF
```

### `coverage.json`

The same `coverage` block as above, standalone. `files_uncovered` is the one to
watch: it names the files that failed passes left unreviewed. An empty report
with a non-empty `files_uncovered` is not a clean repository.

## Library

There is no supported Python API — the module layout is internal and moves
without notice. Shell out to the CLI and read `findings.json`.

```python
import json, subprocess

subprocess.run(["readthrough", "scan", "./my-repo", "--out", "out"], check=True)
findings = json.load(open("out/findings.json"))["findings"]
```
