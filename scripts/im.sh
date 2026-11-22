#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../backend"
uv sync --extra im
uv run python -m app.im.worker &
worker_pid=$!
trap 'kill "$worker_pid" 2>/dev/null || true' EXIT
uv run python -m app.im.adapter
