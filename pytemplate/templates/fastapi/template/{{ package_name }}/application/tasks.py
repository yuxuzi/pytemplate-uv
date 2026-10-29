"""The task-queue port for long-running work such as imports, analyses, or backtests."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

JobFunction = Callable[[], Awaitable[dict[str, object]]]


class JobState(StrEnum):
    """Where a job is in its lifecycle."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass
class Job:
    """One submitted unit of background work."""

    id: str
    name: str
    state: JobState = JobState.QUEUED
    result: dict[str, object] | None = None
    error: str | None = None


class TaskQueue(Protocol):
    """Runs jobs outside the request. Adapters decide where: in process, or on a broker."""

    async def submit(self, name: str, work: JobFunction) -> Job:
        """Queue `work` and return its job immediately."""
        ...

    async def get(self, job_id: str) -> Job | None:
        """Return a job by identifier, or None."""
        ...
