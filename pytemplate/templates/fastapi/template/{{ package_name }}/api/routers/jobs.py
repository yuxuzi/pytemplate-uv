"""Background job endpoints: submit returns 202 at once; poll the job for its result."""

from typing import Self

from fastapi import APIRouter, status
from pydantic import BaseModel

from ...application.examples import ExampleService
from ...application.tasks import Job, JobState
from ...domain.errors import NotFoundError
from ..dependencies import ContainerDep, TaskQueueDep

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobRead(BaseModel):
    """A job's public state."""

    id: str
    name: str
    state: JobState
    result: dict[str, object] | None
    error: str | None

    @classmethod
    def from_job(cls, job: Job) -> Self:
        """Convert a job into its public representation."""
        return cls(id=job.id, name=job.name, state=job.state, result=job.result, error=job.error)


@router.post("/example-count", status_code=status.HTTP_202_ACCEPTED)
async def count_examples(container: ContainerDep, tasks: TaskQueueDep) -> JobRead:
    """Count examples in the background, in a unit of work of its own."""

    async def work() -> dict[str, object]:
        async with container.unit_of_work() as unit_of_work:
            return {"examples": await ExampleService(unit_of_work).count()}

    return JobRead.from_job(await tasks.submit("example-count", work))


@router.get("/{job_id}")
async def get_job(job_id: str, tasks: TaskQueueDep) -> JobRead:
    """Return a job's state and, once finished, its result."""
    job = await tasks.get(job_id)
    if job is None:
        raise NotFoundError("Job", job_id)
    return JobRead.from_job(job)
