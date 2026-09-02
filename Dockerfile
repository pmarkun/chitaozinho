# syntax=docker/dockerfile:1.10@sha256:865e5dd094beca432e8c0a1d5e1c465db5f998dca4e439981029b3b81fb39ed5
FROM ghcr.io/astral-sh/uv:0.11.32@sha256:df4cae8f3a96d175e2e5f992e597550000edbe78fdc2594d5cd8de1a217f504c AS uv
FROM python:3.13.5-slim-bookworm@sha256:4c2cf9917bd1cbacc5e9b07320025bdb7cdf2df7b0ceaccb55e9dd7e30987419 AS builder

ARG SOURCE_DATE_EPOCH
ENV SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH}" \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PYTHON_DOWNLOADS=0
WORKDIR /app

COPY --from=uv /uv /uvx /usr/local/bin/
COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY packages/protocol-py/pyproject.toml packages/protocol-py/pyproject.toml
RUN uv sync --frozen --all-packages --no-dev --no-install-workspace

FROM python:3.13.5-slim-bookworm@sha256:4c2cf9917bd1cbacc5e9b07320025bdb7cdf2df7b0ceaccb55e9dd7e30987419 AS runtime

ARG VCS_REF=unknown
LABEL org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.licenses="Apache-2.0"

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH="/app/src" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

RUN groupadd --system --gid 10001 chitaozinho \
    && useradd --system --uid 10001 --gid chitaozinho --home-dir /app chitaozinho \
    && mkdir -p /app/data \
    && chown chitaozinho:chitaozinho /app/data
COPY --from=builder --chown=chitaozinho:chitaozinho /app/.venv /app/.venv
COPY --chown=chitaozinho:chitaozinho apps/api/src/chitaozinho_api /app/src/chitaozinho_api
COPY --chown=chitaozinho:chitaozinho packages/protocol-py/src/chitaozinho_protocol /app/src/chitaozinho_protocol
COPY --chown=chitaozinho:chitaozinho alembic.ini /app/alembic.ini
COPY --chown=chitaozinho:chitaozinho apps/api/migrations /app/apps/api/migrations
COPY --chown=chitaozinho:chitaozinho infra/openbao/ca.crt /app/infra/openbao/ca.crt
RUN find /app/src -type f -print0 \
    | sort -z \
    | xargs -0 sha256sum \
    | sha256sum \
    | awk '{print "sha256:" $1}' > /app/SOURCE_SHA256 \
    && chown chitaozinho:chitaozinho /app/SOURCE_SHA256

USER chitaozinho
EXPOSE 8000
CMD ["uvicorn", "chitaozinho_api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
