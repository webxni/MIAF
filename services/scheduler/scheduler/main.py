import logging
import os
import signal
import sys
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from apscheduler.schedulers.blocking import BlockingScheduler


def _post(url: str, token: str | None) -> None:
    headers: dict[str, str] = {}
    if token:
        headers["x-automation-token"] = token
    request = Request(url, method="POST", headers=headers)
    with urlopen(request, timeout=15) as response:
        body = response.read().decode("utf-8", errors="replace")
        logging.getLogger("scheduler").info("POST %s -> %s %s", url, response.status, body)


def heartbeat() -> None:
    log = logging.getLogger("scheduler.heartbeat")
    url = os.getenv("API_HEARTBEAT_URL", "http://api:8000/internal/heartbeat/run-defaults")
    token = os.getenv("AUTOMATION_TOKEN")
    try:
        _post(url, token)
        log.info("heartbeat trigger ok date=%s", date.today().isoformat())
    except HTTPError as exc:
        log.error("heartbeat trigger failed status=%s", exc.code)
    except URLError as exc:
        log.error("heartbeat trigger connection failed: %s", exc)


def cleanup_sessions() -> None:
    log = logging.getLogger("scheduler.cleanup")
    base = os.getenv("API_BASE_URL", "http://api:8000")
    url = f"{base}/internal/auth/cleanup-sessions"
    token = os.getenv("AUTOMATION_TOKEN")
    try:
        _post(url, token)
        log.info("session cleanup triggered")
    except HTTPError as exc:
        log.error("session cleanup failed status=%s", exc.code)
    except URLError as exc:
        log.error("session cleanup connection failed: %s", exc)


def main() -> int:
    log_level = os.getenv("LOG_LEVEL", "info").upper()
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log = logging.getLogger("scheduler")

    interval = int(os.getenv("HEARTBEAT_INTERVAL_SECONDS", "300"))

    sched = BlockingScheduler(timezone="UTC")
    sched.add_job(
        heartbeat,
        "interval",
        seconds=interval,
        id="heartbeat",
        max_instances=1,
        coalesce=True,
    )
    sched.add_job(
        cleanup_sessions,
        "cron",
        hour=3,
        minute=0,
        id="session_cleanup",
        max_instances=1,
        coalesce=True,
    )

    def _shutdown(signum, frame):
        log.info("scheduler received signal %s, shutting down", signum)
        sched.shutdown(wait=False)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    log.info("scheduler started; heartbeat every %ss -> %s", interval, os.getenv("API_HEARTBEAT_URL", "http://api:8000/internal/heartbeat/run-defaults"))
    sched.start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
