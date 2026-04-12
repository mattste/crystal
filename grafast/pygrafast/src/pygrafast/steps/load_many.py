"""LoadManyStep - batch loader that returns a list per key."""

from __future__ import annotations

from typing import Any, Callable

from ..step import ExecutionDetails, Step

LoadManyCallback = Callable[[list[Any], Any], list[Any]]


class LoadManyStep(Step[list[Any]]):
    """Batch-loads a list of items per key.

    Given a list of keys, calls the load function once with all keys
    and returns a list of results per key.
    """

    is_sync_and_safe = True

    def __init__(
        self,
        key_step: Step[Any],
        load: LoadManyCallback,
        shared: Step[Any] | None = None,
    ) -> None:
        super().__init__()
        self._load = load
        self._key_dep_id = self.add_dependency(key_step)
        self._shared_dep_id: int | None = None
        if shared is not None:
            self._shared_dep_id = self.add_dependency(shared)
        self._params: dict[str, Step[Any]] = {}

    def set_param(self, name: str, step: Step[Any]) -> None:
        """Set a parameter step (e.g. limit)."""
        self._params[name] = step
        self.add_dependency(step)

    def to_string_meta(self) -> str | None:
        return getattr(self._load, "__name__", None)

    def execute(self, details: ExecutionDetails) -> list[list[Any] | None]:
        keys: list[Any] = []
        for i in range(details.count):
            keys.append(details.values[0].at(i))

        extra = None
        if self._shared_dep_id is not None:
            extra = details.values[1].at(0)

        results = self._load(keys, extra)
        return results


def load_many(
    key_step: Step[Any],
    load: LoadManyCallback | dict[str, Any],
    *,
    shared: Step[Any] | None = None,
) -> LoadManyStep:
    """Create a LoadManyStep."""
    if isinstance(load, dict):
        load_fn = load["load"]
        shared = load.get("shared", shared)
        return LoadManyStep(key_step, load_fn, shared=shared)
    return LoadManyStep(key_step, load, shared=shared)
