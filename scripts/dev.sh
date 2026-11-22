#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -f .env || ! -d frontend/node_modules || ! -d backend/.venv ]]; then
  bash scripts/setup.sh
fi
cd backend
uv sync --locked --extra im
uv run --locked --extra im python -m app.core.preflight
uv run --locked --extra im alembic upgrade head
exec uv run --locked --extra im python -m app.dev
