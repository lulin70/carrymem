FROM python:3.12-slim

LABEL org.opencontainers.image.title="CarryMem MCP Server"
LABEL org.opencontainers.image.description="Your portable AI memory layer — MCP server for memory classification"
LABEL org.opencontainers.image.version="0.2.4"
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

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "from carrymem.integration.layer2_mcp.server import MCPServer; print('OK')" || exit 1

CMD ["python", "-m", "carrymem", "mcp"]
