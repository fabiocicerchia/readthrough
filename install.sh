#!/bin/sh
# One-line installer:
#
#   curl -fsSL https://raw.githubusercontent.com/fabiocicerchia/readthrough/main/install.sh | sh
#
# Prefers pipx (isolated venv, `readthrough` on PATH, upgradable) and falls back to
# `pip install --user`. Set READTHROUGH_REF to install a tag or branch other than
# main.
set -eu

REPO=${READTHROUGH_REPO:-https://github.com/fabiocicerchia/readthrough.git}
REF=${READTHROUGH_REF:-main}
SPEC="git+$REPO@$REF"

have() { command -v "$1" >/dev/null 2>&1; }

if have pipx; then
	echo "installing readthrough with pipx ($REF)"
	pipx install --force "$SPEC"
elif have python3; then
	echo "pipx not found; falling back to pip --user ($REF)"
	python3 -m pip install --user --upgrade "$SPEC"
else
	echo "need python3 (3.10+) or pipx on PATH" >&2
	exit 1
fi

if ! have readthrough; then
	cat >&2 <<-'EOF'

		readthrough installed, but it is not on your PATH.
		pip --user installs into ~/.local/bin — add it:

		    export PATH="$HOME/.local/bin:$PATH"
	EOF
	exit 1
fi

echo
readthrough --help >/dev/null && echo "readthrough installed: $(command -v readthrough)"
echo "set ANTHROPIC_API_KEY, then: readthrough scan ./your-repo --fake"
