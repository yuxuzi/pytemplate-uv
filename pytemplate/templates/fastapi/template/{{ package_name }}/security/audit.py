"""Audit events for security decisions, behind a port so they can go to a real audit store."""

import logging
from dataclasses import dataclass
from typing import Literal, Protocol

logger = logging.getLogger("audit")


@dataclass(frozen=True)
class AuditEvent:
    """One security decision."""

    action: str
    outcome: Literal["allowed", "denied"]
    subject: str | None
    detail: str = ""


class AuditSink(Protocol):
    """Records audit events."""

    async def record(self, event: AuditEvent) -> None:
        """Persist or forward one event."""
        ...


class LoggingAuditSink:
    """Write audit events to the `audit` logger as structured records."""

    async def record(self, event: AuditEvent) -> None:
        """Log one event."""
        logger.info(
            "%s %s: %s",
            event.outcome,
            event.action,
            event.detail,
            extra={"event": event.action, "subject": event.subject, "outcome": event.outcome},
        )
