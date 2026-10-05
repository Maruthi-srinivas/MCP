FROM python:3.12-slim-bookworm

WORKDIR /app

COPY shared /tmp/shared
COPY mcp-servers/analysis-mcp/pyproject.toml /app/pyproject.toml
COPY mcp-servers/analysis-mcp/src /app/src
COPY mcp-servers/analysis-mcp/tests /app/tests

ENV HF_HOME=/opt/hf \
    SENTENCE_TRANSFORMERS_HOME=/opt/hf

RUN pip install --no-cache-dir torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir /tmp/shared ".[test]" \
    && python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    WORKSPACE_ROOT=/workspaces \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

EXPOSE 8002

CMD ["python", "-m", "analysis_mcp.server"]
