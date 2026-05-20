"""Run the worker: ``python -m app.worker``."""

from __future__ import annotations

import asyncio
import logging

from app.core.config import get_settings
from app.worker.runner import run_worker


def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    asyncio.run(run_worker(settings))


if __name__ == "__main__":
    main()
