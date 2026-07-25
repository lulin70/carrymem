# ── Builder stage: build wheel from local source ────────────────────────────
# TD-026: pinned to slim-bookworm (Debian 12) for reproducibility.
# dependabot docker ecosystem (see .github/dependabot.yml) will auto-pin
# to @sha256:<digest> on its next weekly run.
FROM python:3.12-slim-bookworm AS builder

WORKDIR /build

RUN pip install --no-cache-dir --upgrade "pip>=26.1.2" build setuptools wheel setuptools_scm[toml]

# Copy only files needed for building the wheel
COPY setup.py pyproject.toml MANIFEST.in ./
COPY src/ ./src/
COPY bin/ ./bin/
COPY README.md ./

RUN python -m build --wheel --no-isolation

# ── Runtime stage: minimal image with only runtime dependencies ─────────────
# TD-026: same base image pinning as builder stage above.
FROM python:3.12-slim-bookworm

ARG VERSION=0.9.4

LABEL org.opencontainers.image.title="CarryMem MCP Server"
LABEL org.opencontainers.image.description="Your portable AI memory layer — MCP server for memory classification"
LABEL org.opencontainers.image.version="${VERSION}"
LABEL org.opencontainers.image.source="https://github.com/lulin70/carrymem"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CARRYMEM_DATA_PATH=/data \
    CARRYMEM_JSON_LOG=1

WORKDIR /app

# Install runtime dependencies from the locked requirements file (TD-014).
# Using --no-deps ensures pip does not re-resolve the dependency tree —
# every transitive dep is already pinned in requirements.lock for reproducibility.
# The wheel itself is installed with --no-deps as well because its [full] extras
# are already covered by requirements.lock.
COPY requirements.lock /tmp/requirements.lock
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir --upgrade "pip>=26.1.2" && \
    pip install --no-cache-dir --no-deps -r /tmp/requirements.lock && \
    whl=$(ls /tmp/carrymem-*.whl | head -1) && \
    pip install --no-cache-dir --no-deps "${whl}" && \
    rm -f /tmp/*.whl /tmp/requirements.lock

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
    CMD python -c "from carrymem import CarryMem; cm = CarryMem(); cm.close(); print('OK')" || exit 1

# Default: stdio transport (for MCP clients like Claude Code, Cursor, etc.)
# This mode communicates via stdin/stdout, not HTTP.
CMD ["python", "-m", "carrymem", "mcp"]
