"""Spelling suggestions for unknown identifiers in error messages."""

from __future__ import annotations

from collections.abc import Iterable
from difflib import get_close_matches


def closest(value: str, candidates: Iterable[str]) -> str | None:
    """Return the candidate most similar to ``value``, or ``None`` when none is close."""
    matches = get_close_matches(value, list(candidates), n=1, cutoff=0.6)
    return matches[0] if matches else None


def did_you_mean(value: str, candidates: Iterable[str]) -> str:
    """Return ``" Did you mean 'x'?"`` for the closest candidate, or an empty string."""
    match = closest(value, candidates)
    return f" Did you mean '{match}'?" if match else ""
