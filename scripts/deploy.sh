#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
test -f .env || { echo '请先创建并配置 .env'; exit 1; }
docker compose up --build -d
