# syntax=docker/dockerfile:1-labs

ARG CUSTOM_CERT_DIR="certs"

FROM python:3.11-slim AS py_deps
WORKDIR /api
COPY pyproject.toml poetry.lock ./
RUN --mount=type=cache,target=/root/.cache/pip python -m pip install poetry==2.0.1 --no-cache-dir && \
    poetry config virtualenvs.create true --local && \
    poetry config virtualenvs.in-project true --local && \
    poetry config virtualenvs.options.always-copy true --local && \
    POETRY_MAX_WORKERS=10 poetry install --no-interaction --no-ansi --only main && \
    poetry cache clear --all

FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN if [ -n "${CUSTOM_CERT_DIR}" ]; then \
        mkdir -p /usr/local/share/ca-certificates && \
        if [ -d "${CUSTOM_CERT_DIR}" ]; then \
            cp -r ${CUSTOM_CERT_DIR}/* /usr/local/share/ca-certificates/ 2>/dev/null || true; \
            update-ca-certificates; \
        fi \
    fi

ENV PATH="/opt/venv/bin:$PATH"
COPY --from=py_deps /api/.venv /opt/venv
COPY api/ ./api/
EXPOSE ${PORT:-8001}

RUN echo '#!/bin/bash\n\
if [ -f .env ]; then\n\
  export $(grep -v "^#" .env | xargs -r)\n\
fi\n\
if [ -z "$OPENAI_API_KEY" ] || [ -z "$GOOGLE_API_KEY" ]; then\n\
  echo "Warning: OPENAI_API_KEY and/or GOOGLE_API_KEY environment variables are not set."\n\
fi\n\
python -m api.server.main --port ${PORT:-8001}' > /app/start.sh && chmod +x /app/start.sh

ENV PORT=8001
ENV SERVER_BASE_URL=http://localhost:${PORT:-8001}
RUN touch .env
CMD ["/app/start.sh"]