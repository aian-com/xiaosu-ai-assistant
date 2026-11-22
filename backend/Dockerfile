FROM node:24-bookworm-slim AS frontend
WORKDIR /workspace/frontend
RUN corepack enable
COPY frontend/ ./
RUN corepack pnpm install --frozen-lockfile && corepack pnpm build

FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:0.8.3 /uv /usr/local/bin/uv
WORKDIR /workspace/backend
COPY backend/ ./
RUN uv sync --locked --no-dev --extra im
COPY --from=frontend /workspace/backend/static ./static
ENV PATH="/workspace/backend/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
