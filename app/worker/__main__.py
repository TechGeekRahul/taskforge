"""Run the worker: ``python -m app.worker``."""

from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.worker.runner import run_worker


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    asyncio.run(run_worker(settings))


if __name__ == "__main__":
    main()
