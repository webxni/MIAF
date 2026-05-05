"""CLI entrypoint: `python -m app.cli <command>`.

Commands:
    seed     — idempotent seed (tenant, user, personal+business entities, default COAs)
    migrate  — alembic upgrade head
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys

from app.config import get_settings


def _setup_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


async def _seed() -> int:
    from app.db import SessionLocal
    from app.services.seed import run_seed

    async with SessionLocal() as db:
        result = await run_seed(db)
        await db.commit()
    print(json.dumps(result, indent=2))
    return 0


def _migrate() -> int:
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    return 0


def main(argv: list[str] | None = None) -> int:
    _setup_logging()
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage: python -m app.cli <seed|migrate>", file=sys.stderr)
        return 2
    cmd = args[0]
    if cmd == "seed":
        return asyncio.run(_seed())
    if cmd == "migrate":
        return _migrate()
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
