# syntax=docker/dockerfile:1
#
# Husk container image (published to ghcr.io/husk-ai-team/husk-ai).
# Two stages: a Node stage builds the Studio bundle (apps/studio/dist is
# gitignored, so it must be built), and a uv/Python stage runs the backend
# which serves that bundle. Run:
#
#   docker run --rm -p 7654:7654 -v husk-data:/data ghcr.io/husk-ai-team/husk-ai
#
# then open http://localhost:7654 (seed sample data with:
#   docker exec <container> uv run --no-sync husk-ai demo).

# --- Stage 1: build the Studio --------------------------------------------------
FROM node:20-bookworm-slim AS studio
WORKDIR /app
RUN corepack enable
COPY . .
RUN corepack pnpm install --frozen-lockfile
RUN corepack pnpm --filter studio build   # -> /app/apps/studio/dist

# --- Stage 2: Python runtime ----------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS runtime
WORKDIR /app
ENV HUSK_HOME=/data \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
# Install the Python workspace (runtime deps only) from the committed lockfile.
COPY . .
RUN uv sync --frozen --all-packages --no-dev
# Drop in the Studio bundle the backend serves at apps/studio/dist.
COPY --from=studio /app/apps/studio/dist ./apps/studio/dist
VOLUME ["/data"]
EXPOSE 7654
# --no-sync: the env is already synced above; don't re-resolve at boot.
CMD ["uv", "run", "--no-sync", "husk-ai", "start", "--host", "0.0.0.0", "--no-open-browser"]
