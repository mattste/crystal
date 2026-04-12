"""get() helper - shorthand for AccessStep with a single key."""

from __future__ import annotations

from typing import Any

from ..step import Step
from .access import AccessStep


def get(step: Step[Any], key: str) -> AccessStep:
    """Create an AccessStep for a single property key."""
    return AccessStep(step, [key])
