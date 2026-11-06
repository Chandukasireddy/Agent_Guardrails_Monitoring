FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 VAULT_HOST=0.0.0.0 VAULT_OPEN_BROWSER=false

COPY pyproject.toml uv.lock* README.md ./
COPY vault_heist ./vault_heist
RUN uv sync --no-dev --extra langfuse

COPY config ./config
COPY extensions ./extensions
COPY guardrails ./guardrails
COPY web ./web

EXPOSE 8000
CMD ["uv", "run", "--no-dev", "vault-heist", "serve", "--no-browser"]
