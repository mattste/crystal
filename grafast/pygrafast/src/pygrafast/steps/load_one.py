"""LoadOneStep - batch loader for single items."""

from __future__ import annotations

from typing import Any, Callable, TypeVar

from ..step import ExecutionDetails, Step

TKey = TypeVar("TKey")
TData = TypeVar("TData")

# LoadOneCallback: (keys: list[TKey], extra) -> list[TData | None]
LoadOneCallback = Callable[[list[Any], Any], list[Any]]


class LoadOneStep(Step[Any]):
    """Batch-loads a single item per key.

    Given a list of keys, calls the load function once with all keys
    and returns the corresponding results.
    """

    is_sync_and_safe = True

    def __init__(
        self,
        key_step: Step[Any],
        load: LoadOneCallback,
        shared: Step[Any] | None = None,
    ) -> None:
        super().__init__()
        self._load = load
        self._key_dep_id = self.add_dependency(key_step)
        self._shared_dep_id: int | None = None
        if shared is not None:
            self._shared_dep_id = self.add_dependency(shared)

    def to_string_meta(self) -> str | None:
        name = getattr(self._load, "__name__", None)
        return name

    def execute(self, details: ExecutionDetails) -> list[Any]:
        # Collect all keys
        keys: list[Any] = []
        for i in range(details.count):
            keys.append(details.values[0].at(i))

        # Build extra dict with shared value
        extra: dict[str, Any] = {}
        if self._shared_dep_id is not None:
            extra["shared"] = details.values[1].at(0)

        # Call the batch loader
        results = self._load(keys, extra)

        return results


def load_one(
    key_step: Step[Any],
    load: LoadOneCallback | dict[str, Any],
    *,
    shared: Step[Any] | None = None,
) -> LoadOneStep:
    """Create a LoadOneStep.

    Can be called as:
        load_one($id, batch_fn)
        load_one($id, {"load": batch_fn, "shared": $db})
    """
    if isinstance(load, dict):
        load_fn = load["load"]
        shared = load.get("shared", shared)
        return LoadOneStep(key_step, load_fn, shared=shared)
    return LoadOneStep(key_step, load, shared=shared)
