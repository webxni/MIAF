import logging
import os
import sys

from redis import Redis
from rq import Queue, Worker

QUEUES = ["finclaw-default"]


def main() -> int:
    log_level = os.getenv("LOG_LEVEL", "info").upper()
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log = logging.getLogger("worker")

    redis_url = os.environ["REDIS_URL"]
    conn = Redis.from_url(redis_url)
    conn.ping()
    log.info("worker connected to redis; listening on %s", QUEUES)

    queues = [Queue(name, connection=conn) for name in QUEUES]
    worker = Worker(queues, connection=conn)
    worker.work(with_scheduler=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
