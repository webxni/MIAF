import logging
import os
import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler


def heartbeat() -> None:
    logging.getLogger("scheduler.heartbeat").info("tick")


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

    log.info("scheduler started; heartbeat every %ss", interval)
    sched.start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
