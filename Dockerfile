FROM python:3.12-slim

ARG VERSION=0.4.0

LABEL org.opencontainers.image.title="CarryMem MCP Server"
LABEL org.opencontainers.image.description="Your portable AI memory layer — MCP server for memory classification"
LABEL org.opencontainers.image.version="${VERSION}"
LABEL org.opencontainers.image.source="https://github.com/lulin70/carrymem"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CARRYMEM_DATA_PATH=/data

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir carrymem[full]

COPY . .

RUN mkdir -p /data

VOLUME ["/data"]

# EXPOSE 8765 for HTTP+SSE mode (carrymem serve).
# Default CMD uses stdio transport which does NOT listen on any HTTP port.
# To use HTTP mode, override CMD: docker run carrymem python -m carrymem serve
# Monitoring endpoints in HTTP mode: /health, /healthz, /metrics
EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "from carrymem import CarryMem; print('OK')" || exit 1

# Default: stdio transport (for MCP clients like Claude Code, Cursor, etc.)
# This mode communicates via stdin/stdout, not HTTP.
CMD ["python", "-m", "carrymem", "mcp"]
