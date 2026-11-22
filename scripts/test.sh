#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../backend"
if [[ "${1:-}" == "--smoke" ]]; then
  uv run --locked python -m tests.smoke_local
  exit 0
fi
uv run --locked pytest -q
if [[ "${1:-}" == "--backend" ]]; then exit 0; fi
cd ../frontend
if command -v pnpm >/dev/null 2>&1; then
  pnpm build
else
  powershell.exe -NoProfile -Command 'pnpm build; exit $LASTEXITCODE'
fi
