"""An in-process `TaskQueue`: asyncio tasks bounded by a semaphore. Jobs do not survive a
restart; replace this adapter with a broker-backed one when they must."""

import asyncio
import logging
import uuid

from ..application.tasks import Job, JobFunction, JobState

logger = logging.getLogger(__name__)


class InProcessTaskQueue:
    """Run jobs concurrently in this process, at most `max_concurrency` at a time."""

    def __init__(self, max_concurrency: int = 4) -> None:
        self._slots = asyncio.Semaphore(max_concurrency)
        self._jobs: dict[str, Job] = {}
        self._running: set[asyncio.Task[None]] = set()

    async def submit(self, name: str, work: JobFunction) -> Job:
        """Start `work` in the background and return its job."""
        job = Job(id=uuid.uuid4().hex, name=name)
        self._jobs[job.id] = job
        task = asyncio.create_task(self._run(job, work), name=f"job-{name}-{job.id}")
        self._running.add(task)
        task.add_done_callback(self._running.discard)
        return job

    async def get(self, job_id: str) -> Job | None:
        """Return a job by identifier, or None."""
        return self._jobs.get(job_id)

    async def drain(self) -> None:
        """Wait for every running job (useful in tests and at shutdown)."""
        while self._running:
            await asyncio.gather(*self._running, return_exceptions=True)

    async def shutdown(self) -> None:
        """Cancel unfinished jobs and wait for them to stop."""
        for task in self._running:
            task.cancel()
        await self.drain()

    async def _run(self, job: Job, work: JobFunction) -> None:
        async with self._slots:
            job.state = JobState.RUNNING
            try:
                job.result = await work()
                job.state = JobState.SUCCEEDED
            except asyncio.CancelledError:
                job.state = JobState.FAILED
                job.error = "cancelled"
                raise
            except Exception as error:
                logger.exception("Job %s (%s) failed", job.name, job.id)
                job.state = JobState.FAILED
                job.error = type(error).__name__
