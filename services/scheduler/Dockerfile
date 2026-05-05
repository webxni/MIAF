# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/srv/scheduler

WORKDIR /srv/scheduler

RUN apt-get update && apt-get install -y --no-install-recommends tini \
 && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 1001 app \
 && useradd --system --uid 1001 --gid app --home /srv/scheduler --shell /bin/bash app

COPY services/scheduler/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

COPY services/scheduler /srv/scheduler
RUN chown -R app:app /srv/scheduler

USER app

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "scheduler.main"]
