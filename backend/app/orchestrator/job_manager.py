"""Background job manager with bounded workers and GPU locking."""

from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class GpuLock:
    """Ensure only one VRAM-heavy model stage runs at a time."""

    _lock: threading.Lock = field(default_factory=threading.Lock)

    def acquire(self, timeout: float | None = None) -> bool:
        if timeout is None:
            self._lock.acquire()
            return True
        return self._lock.acquire(timeout=timeout)

    def release(self) -> None:
        self._lock.release()


class JobManager:
    def __init__(self, max_workers: int | None = None) -> None:
        settings = get_settings()
        self.max_workers = max(1, max_workers or settings.max_concurrent_jobs)
        self.gpu_lock = GpuLock()
        self._cancel_flags: dict[str, threading.Event] = {}
        self._futures: dict[str, Future[None]] = {}
        self._executor = ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="avc-job",
        )
        self._lock = threading.Lock()

    def request_cancel(self, job_id: str) -> None:
        event = self._cancel_flags.setdefault(job_id, threading.Event())
        event.set()

    def clear_cancel(self, job_id: str) -> None:
        self._cancel_flags.pop(job_id, None)
        with self._lock:
            self._futures.pop(job_id, None)

    def is_cancelled(self, job_id: str) -> bool:
        event = self._cancel_flags.get(job_id)
        return bool(event and event.is_set())

    def submit(self, job_id: str, fn: Callable[[], None]) -> Future[None]:
        with self._lock:
            existing = self._futures.get(job_id)
            if existing and not existing.done():
                logger.warning("Job %s already running; ignoring duplicate submit", job_id)
                return existing

            def _runner() -> None:
                try:
                    fn()
                except Exception:
                    logger.exception("Unhandled error in job %s", job_id)
                    raise

            future = self._executor.submit(_runner)
            self._futures[job_id] = future
            return future

    def submit_analyze(self, job_id: str) -> Future[None]:
        from app.orchestrator.pipeline import run_phase2_analyze_job

        return self.submit(job_id, lambda: run_phase2_analyze_job(job_id))

    def submit_render(self, job_id: str) -> Future[None]:
        from app.orchestrator.render_pipeline import run_render_job

        return self.submit(job_id, lambda: run_render_job(job_id))

    def submit_batch_export(self, job_id: str) -> Future[None]:
        from app.orchestrator.render_pipeline import run_batch_export_job

        return self.submit(job_id, lambda: run_batch_export_job(job_id))

    def submit_diarize(self, job_id: str) -> Future[None]:
        from app.orchestrator.diarize_pipeline import run_diarize_job

        return self.submit(job_id, lambda: run_diarize_job(job_id))

    def shutdown(self, wait: bool = False) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=True)


job_manager = JobManager()
