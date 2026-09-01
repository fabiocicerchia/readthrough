#!/bin/sh
# Scan this repository with itself, offline. No API key, no network, no cost.
set -eu

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)
OUT=${1:-/tmp/readthrough-example}

cd "$ROOT"
python3 -m readthrough scan . \
	--fake \
	--out "$OUT" \
	--exclude 'tests/*' \
	--exclude 'examples/*'

echo
echo "--- coverage, from the top of report.md ---"
sed -n '1,40p' "$OUT/report.md"
echo
echo "full report:   $OUT/report.md"
echo "machine-readable: $OUT/findings.json, $OUT/findings.sarif"
