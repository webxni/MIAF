# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/srv/api

WORKDIR /srv/api

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl tini tesseract-ocr tesseract-ocr-eng tesseract-ocr-spa \
 && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN groupadd --system --gid 1001 app \
 && useradd --system --uid 1001 --gid app --home /srv/api --shell /bin/bash app

COPY apps/api/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# --- dev stage ---------------------------------------------------------------
FROM base AS dev

# Source is bind-mounted from compose; we still copy as a fallback for `docker run`.
COPY apps/api /srv/api
RUN chown -R app:app /srv/api
USER app

EXPOSE 8000
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# --- prod stage --------------------------------------------------------------
FROM base AS prod

COPY apps/api /srv/api
RUN chown -R app:app /srv/api
USER app

EXPOSE 8000
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 --proxy-headers --forwarded-allow-ips \"${UVICORN_FORWARDED_IPS:-*}\""]
