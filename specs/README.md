# Specifications of readthrough

What this code does, one atomic Gherkin scenario per behaviour, read from the code by code-atlas.
Tags: `@verified` a test asserts it · `@inferred` read from the code only · `@gap` an entry point no test covers · `@human` written or amended by a person, never rewritten.

## Analysis
The focused review passes the model runs over each chunk of code.

- **Lens catalog**: [Choosing review lenses](analysis/lens-catalog/lens-catalog.feature) (4), [Listing review lenses](analysis/lens-catalog/listing-lenses.feature) (1)
- **Response parsing**: [Reading findings from the model's reply](analysis/response-parsing/reading-model-findings.feature) (3)

## Codebase intake
How a repository is turned into a complete, accounted-for set of reviewable pieces before any analysis runs.

- **Chunking**: [Reviewing large files in overlapping windows](codebase-intake/chunking/chunking.feature) (1)
- **File discovery**: [Finding the files to audit](codebase-intake/file-discovery/file-discovery.feature) (2)
- **File filtering and skip reasons**: [Deciding which files get reviewed](codebase-intake/file-filtering/file-filtering.feature) (4)

## Command line
How users invoke readthrough and what it tells them.

- **Commands and options**: [Starting a scan of one repository](command-line/commands-and-options/starting-a-scan.feature) (7)
- **Entry points**: [Launching readthrough](command-line/entry-points/launching-readthrough.feature) (1)
- **Exit codes**: [Interrupting a scan and the exit status](command-line/exit-codes/interrupting-a-scan.feature) (3)
- **Progress and console output**: [Keeping results and diagnostics on separate output streams](command-line/progress-and-output/output-streams.feature) (1)

## Findings
Turning raw per-pass findings into a deduplicated, ranked and checked list.

- **Corroboration**: [Corroborating findings](findings/corroboration/corroborating-findings.feature) (1)
- **Deduplication**: [Merging duplicate findings](findings/deduplication/merging-duplicate-findings.feature) (5)
- **Prioritisation**: [Prioritising findings](findings/prioritisation/prioritising-findings.feature) (2)
- **Verification**: [Second-opinion verification during a scan](findings/verification/scan-verification.feature) (2)

## Installation and distribution
Getting readthrough onto a machine or into a pipeline.

- **Container image**: [Running readthrough from the container image](installation/container-image/container-image.feature) (6)
- **One-line installer**: [Installing readthrough with the one-line installer](installation/one-line-installer/one-line-installer.feature) (6)
- **Packages**: [Installing readthrough from a working tree](installation/packages/install-from-working-tree.feature) (4)

## Reporting
Presenting scan results to people and to other tools.

- **Coverage reporting**: [Showing what was and was not reviewed](reporting/coverage-reporting/coverage-reporting.feature) (5)
- **Machine-readable exports**: [Exporting findings for CI and code scanning](reporting/machine-exports/machine-exports.feature) (4)
- **Markdown report**: [Reading the audit report](reporting/markdown-report/markdown-report.feature) (6)
- **Report rebuild**: [Rebuilding reports from an earlier scan](reporting/report-rebuild/rebuilding-reports.feature) (3)

## Scan runs
Running an audit end to end over one or many repositories and keeping its state.

- **Multi-repository scan**: [Scanning a fleet of repositories](scan-runs/multi-scan/multi-repository-scan.feature) (4)
