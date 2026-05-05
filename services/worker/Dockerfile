# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/srv/worker

WORKDIR /srv/worker

RUN apt-get update && apt-get install -y --no-install-recommends tini \
 && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 1001 app \
 && useradd --system --uid 1001 --gid app --home /srv/worker --shell /bin/bash app

COPY services/worker/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

COPY services/worker /srv/worker
RUN chown -R app:app /srv/worker

USER app

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "worker.main"]
