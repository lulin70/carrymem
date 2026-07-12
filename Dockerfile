# ── Builder stage: build wheel from local source ────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

RUN pip install --no-cache-dir --upgrade pip build

# Copy only files needed for building the wheel
COPY setup.py pyproject.toml MANIFEST.in ./
COPY src/ ./src/
COPY README.md ./

RUN python -m build --wheel --no-isolation

# ── Runtime stage: minimal image with only runtime dependencies ─────────────
FROM python:3.12-slim

ARG VERSION=0.7.2

LABEL org.opencontainers.image.title="CarryMem MCP Server"
LABEL org.opencontainers.image.description="Your portable AI memory layer — MCP server for memory classification"
LABEL org.opencontainers.image.version="${VERSION}"
LABEL org.opencontainers.image.source="https://github.com/lulin70/carrymem"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CARRYMEM_DATA_PATH=/data

WORKDIR /app

# Install the wheel built in the builder stage (includes [full] extras)
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir --upgrade pip && \
    whl=$(ls /tmp/carrymem-*.whl | head -1) && \
    pip install --no-cache-dir "${whl}[full]" && \
    rm -f /tmp/*.whl

# Create non-root user for security (P1-10 fix)
RUN groupadd -r carrymem && useradd -r -g carrymem -d /app -s /sbin/nologin carrymem && \
    mkdir -p /data && chown -R carrymem:carrymem /data /app

USER carrymem

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
