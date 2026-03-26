FROM python:3.14-slim

ARG SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0-dev

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir .

CMD ["bifrost"]
