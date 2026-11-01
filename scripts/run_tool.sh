#!/usr/bin/env bash
# Wrapper: python -m finance.cli dengan venv + PYTHONPATH proyek.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
exec .venv/bin/python -m finance.cli "$@"
