FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY apps/api/pyproject.toml /app/pyproject.toml
COPY shared /tmp/shared
COPY apps/api/src /app/src
COPY apps/api/migrations /app/migrations
COPY apps/api/tests /app/tests
COPY mcp-servers/analysis-mcp/tests/fixtures/service_app /opt/fixtures/service_app
COPY mcp-servers/repository-mcp/tests/fixtures/injection_repo /opt/fixtures/injection_repo

RUN pip install --no-cache-dir /tmp/shared ".[test]"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MIGRATIONS_DIR=/app/migrations

EXPOSE 8004

CMD ["python", "-m", "api_app.server"]
