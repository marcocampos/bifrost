FROM python:3.14-slim

ARG SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0-dev

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir . \
    && useradd --system --no-create-home bifrost

USER bifrost

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8080/')"]

CMD ["bifrost"]
