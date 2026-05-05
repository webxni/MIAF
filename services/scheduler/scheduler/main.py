import logging
import os
import signal
import sys
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from apscheduler.schedulers.blocking import BlockingScheduler


def heartbeat() -> None:
    log = logging.getLogger("scheduler.heartbeat")
    url = os.getenv("API_HEARTBEAT_URL", "http://api:8000/internal/heartbeat/run-defaults")
    token = os.getenv("AUTOMATION_TOKEN")
    headers = {}
    if token:
        headers["x-automation-token"] = token
    request = Request(url, method="POST", headers=headers)
    try:
        with urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8", errors="replace")
            log.info("heartbeat trigger ok date=%s status=%s body=%s", date.today().isoformat(), response.status, body)
    except HTTPError as exc:
        log.error("heartbeat trigger failed status=%s", exc.code)
    except URLError as exc:
        log.error("heartbeat trigger connection failed: %s", exc)


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
