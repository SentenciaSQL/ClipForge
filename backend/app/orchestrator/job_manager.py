"""Background job manager skeleton.

Phase 1 persists jobs and exposes status. Phase 2+ executes pipeline stages
on a bounded worker pool with GPU resource locking.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class GpuLock:
    """Ensure only one VRAM-heavy model stage runs at a time."""

    _lock: threading.Lock = field(default_factory=threading.Lock)

    def acquire(self, timeout: float | None = None) -> bool:
        return self._lock.acquire(timeout=timeout) if timeout is not None else self._lock.acquire()

    def release(self) -> None:
        self._lock.release()


class JobManager:
    def __init__(self, max_workers: int = 1) -> None:
        self.max_workers = max_workers
        self.gpu_lock = GpuLock()
        self._cancel_flags: dict[str, threading.Event] = {}

    def request_cancel(self, job_id: str) -> None:
        event = self._cancel_flags.setdefault(job_id, threading.Event())
        event.set()

    def is_cancelled(self, job_id: str) -> bool:
        event = self._cancel_flags.get(job_id)
        return bool(event and event.is_set())


job_manager = JobManager()
