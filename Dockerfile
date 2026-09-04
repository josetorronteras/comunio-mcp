FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Ownership proof for the MCP Registry: the value must match "name" in server.json,
# or publishing the OCI package is rejected.
LABEL io.modelcontextprotocol.server.name="io.github.josetorronteras/comunio"
LABEL org.opencontainers.image.title="Comunio MCP" \
      org.opencontainers.image.description="MCP server for Comunio, the online football fantasy manager" \
      org.opencontainers.image.source="https://github.com/josetorronteras/comunio-mcp" \
      org.opencontainers.image.licenses="MIT"

WORKDIR /app

# Dependency metadata first, so edits to the source do not invalidate the
# dependency layer.
COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --editable ".[dev]"

# stdio transport: the client talks to this process over stdin/stdout.
ENTRYPOINT ["comunio-mcp"]
