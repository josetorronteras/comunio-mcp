FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependency metadata first, so edits to the source do not invalidate the
# dependency layer.
COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --editable ".[dev]"

# stdio transport: the client talks to this process over stdin/stdout.
ENTRYPOINT ["comunio-mcp"]
