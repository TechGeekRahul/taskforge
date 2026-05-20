"""Worker main loop — blocking dequeue and task processing."""

from __future__ import annotations

import asyncio
import logging
import signal
from datetime import datetime, timezone

import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.core.config import Settings, get_settings
from app.db.session import async_session_factory, dispose_engine
from app.queue.task_queue import TaskQueue
from app.worker.processor import TaskProcessor

logger = logging.getLogger(__name__)


class WorkerRunner:
    """Pull messages from Redis and process them until stopped."""

    def __init__(
        self,
        redis: Redis,
        settings: Settings | None = None,
    ) -> None:
        self._redis = redis
        self._settings = settings or get_settings()
        self._queue = TaskQueue.from_settings(redis, self._settings)
        self._stop = asyncio.Event()

    def request_stop(self) -> None:
        self._stop.set()

    def install_signal_handlers(self) -> None:
        """Register SIGINT/SIGTERM to stop the loop gracefully."""
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self.request_stop)
            except NotImplementedError:
                # Windows ProactorEventLoop does not support all signals.
                signal.signal(sig, lambda _s, _f: self.request_stop())

    async def run(self) -> None:
        """Run until ``request_stop`` is called."""
        session_factory = async_session_factory(self._settings)
        timeout = self._settings.worker_brpop_timeout

        logger.info(
            "worker started queue=%s brpop_timeout=%ss",
            self._settings.task_queue_key,
            timeout,
        )

        while not self._stop.is_set():
            await self._touch_heartbeat()
            released = await self._queue.release_due_retries()
            if released:
                logger.debug("released %s delayed retry message(s)", released)

            message = await self._queue.dequeue(timeout=timeout)
            if message is None:
                continue

            async with session_factory() as session:
                processor = TaskProcessor(session, redis=self._redis, settings=self._settings)
                try:
                    await processor.process(message)
                    await session.commit()
                except Exception:
                    await session.rollback()
                    logger.exception(
                        "unhandled error processing task_id=%s",
                        message.task_id,
                    )

        logger.info("worker stopped")

    async def _touch_heartbeat(self) -> None:
        await self._redis.set(
            self._settings.worker_heartbeat_key,
            datetime.now(timezone.utc).isoformat(),
            ex=self._settings.worker_heartbeat_ttl_seconds,
        )


async def run_worker(settings: Settings | None = None) -> None:
    """Entry coroutine: connect Redis, run loop, clean up."""
    cfg = settings or get_settings()
    redis = aioredis.from_url(str(cfg.redis_url), decode_responses=True)
    runner = WorkerRunner(redis=redis, settings=cfg)
    runner.install_signal_handlers()

    try:
        await runner.run()
    finally:
        await redis.aclose()
        await dispose_engine()
