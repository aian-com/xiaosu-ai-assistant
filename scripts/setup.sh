#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -f .env ]]; then cp .env.example .env; fi
(cd backend && uv sync --locked --extra im)
(cd frontend && if command -v pnpm >/dev/null 2>&1; then pnpm install --frozen-lockfile; elif command -v corepack >/dev/null 2>&1; then corepack pnpm install --frozen-lockfile; else echo "请安装 Node.js 和 pnpm，并将其加入 PATH。" >&2; exit 1; fi)
echo "本地依赖已准备，数据库自动创建。执行 bash scripts/dev.sh 启动。"
