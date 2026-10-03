FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY shared /tmp/shared
COPY mcp-servers/git-mcp/pyproject.toml /app/pyproject.toml
COPY mcp-servers/git-mcp/src /app/src
COPY mcp-servers/git-mcp/tests /app/tests

RUN pip install --no-cache-dir /tmp/shared ".[test]"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    WORKSPACE_ROOT=/workspaces

EXPOSE 8001

CMD ["python", "-m", "git_mcp.server"]
