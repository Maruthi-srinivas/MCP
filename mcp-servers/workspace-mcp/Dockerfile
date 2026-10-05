FROM python:3.12-slim-bookworm

WORKDIR /app

COPY shared /tmp/shared
COPY mcp-servers/workspace-mcp/pyproject.toml /app/pyproject.toml
COPY mcp-servers/workspace-mcp/src /app/src
COPY mcp-servers/workspace-mcp/tests /app/tests

RUN pip install --no-cache-dir /tmp/shared ".[test]"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    WORKSPACE_ROOT=/workspaces

EXPOSE 8005

CMD ["python", "-m", "workspace_mcp.server"]
