FROM python:3.12-slim-bookworm

WORKDIR /app

COPY agent/pyproject.toml /app/pyproject.toml
COPY agent/src /app/src
COPY agent/tests /app/tests

RUN pip install --no-cache-dir ".[test]"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8003

CMD ["python", "-m", "agent_app.server"]
