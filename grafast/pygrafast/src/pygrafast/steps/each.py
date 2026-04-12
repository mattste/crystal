"""each() - map over a list, applying a plan function per item.

This is a simplified version that doesn't use the full __ListTransformStep /
subroutine LayerPlan approach yet. Instead, it creates a step that:
1. Takes a list from its dependency
2. For each item, runs a callback to create a sub-step plan
3. At execution time, iterates and applies the sub-plan

For Tracer 4, we implement a simpler approach: each() creates an EachStep
that stores the sub-plan callback and at execution time iterates over the
list and batch-executes the sub-step for all items.
"""

from __future__ import annotations

from typing import Any, Callable

from ..step import ExecutionDetails, Step
from .item_step import ItemStep


class EachStep(Step[list[Any]]):
    """Maps over a list, applying a step plan function per item.

    The callback is called during planning to produce a sub-step.
    The sub-step's dependency is an ItemStep representing each list element.
    At execution time, the list is iterated, and the sub-step is executed
    for each batch of items.
    """

    is_sync_and_safe = True

    def __init__(
        self,
        list_step: Step[list[Any]],
        callback: Callable[[Step[Any]], Step[Any]],
    ) -> None:
        super().__init__()
        self._list_dep_id = self.add_dependency(list_step)
        self._callback = callback

        # Create an ItemStep and call the callback during planning
        from ..engine.with_global_layer_plan import with_global_layer_plan

        def plan_subroutine() -> None:
            item_step = ItemStep(list_step)
            self._item_step = item_step
            result_step = callback(item_step)
            self._result_step = result_step

        with_global_layer_plan(self.layer_plan, None, plan_subroutine)

    def to_string_meta(self) -> str | None:
        return f"each({self._result_step})"

    def execute(self, details: ExecutionDetails) -> list[list[Any] | None]:
        """Execute by iterating over each list and batch-executing the sub-step."""
        results: list[list[Any] | None] = []
        # Get parent bucket reference for copying unary values
        parent_bucket = getattr(details, '_bucket', None)

        for i in range(details.count):
            list_value = details.values[0].at(i)

            if list_value is None:
                results.append(None)
                continue

            if not isinstance(list_value, (list, tuple)):
                results.append(None)
                continue

            if len(list_value) == 0:
                results.append([])
                continue

            from ..engine.execute_bucket import Bucket

            sub_bucket = Bucket(self.layer_plan, len(list_value))

            # Store list items in the item_step's slot
            sub_bucket.store[self._item_step.id] = list(list_value)

            # Copy unary values from the parent bucket for steps that
            # sub-steps may depend on (e.g., ContextStep, ValueStep)
            if parent_bucket is not None:
                for step in self.operation_plan.step_tracker.all_steps():
                    if step._no_exec and step._is_unary:
                        if step.id in parent_bucket.store:
                            sub_bucket.store[step.id] = parent_bucket.store[step.id]
                        else:
                            # For ContextSteps created during sub-plan,
                            # look for a matching value in any parent ContextStep
                            from .context_step import ContextStep
                            if isinstance(step, ContextStep):
                                # Find any context value from parent
                                for pid, pval in parent_bucket.store.items():
                                    parent_step = self.operation_plan.step_tracker.get_step_by_id(pid)
                                    if isinstance(parent_step, ContextStep):
                                        sub_bucket.store[step.id] = pval
                                        break

            self._execute_substeps(sub_bucket, list_value)

            result_values = sub_bucket.store.get(self._result_step.id)
            if isinstance(result_values, list):
                results.append(result_values)
            else:
                results.append([result_values] * len(list_value) if result_values is not None else None)

        return results

    def _execute_substeps(self, bucket: Bucket, items: list[Any] | tuple[Any, ...]) -> None:
        """Execute the sub-step chain for a batch of list items."""
        from ..engine.execute_bucket import _execute_step
        from ..step import ExecutionValue

        # We need to walk from item_step through to result_step,
        # executing each step in the chain.
        # Build the set of steps we need to execute (topological order)
        steps_to_execute = self._collect_substeps()

        for step in steps_to_execute:
            if step._no_exec:
                continue
            _execute_step(step, bucket)

    def _collect_substeps(self) -> list[Step[Any]]:
        """Collect all steps between item_step and result_step in topological order."""
        # BFS from item_step through dependents to result_step
        needed: set[int] = set()
        result_id = self._result_step.id
        item_id = self._item_step.id

        # Walk backwards from result_step to find all deps
        def collect_deps(step: Step[Any]) -> None:
            if step.id in needed:
                return
            if step.id == item_id:
                needed.add(step.id)
                return
            needed.add(step.id)
            for dep in step.dependencies:
                collect_deps(dep)

        collect_deps(self._result_step)

        # Sort by id (registration order = topological order for our simple case)
        all_steps = self.operation_plan.step_tracker.all_steps()
        return [s for s in all_steps if s.id in needed and s.id != item_id]


def each(
    list_step: Step[list[Any]],
    callback: Callable[[Step[Any]], Step[Any]],
) -> EachStep:
    """Map over a list step, applying the callback to plan each item.

    Usage:
        each($friends_list, lambda $friend_id: load_one($friend_id, batch_fn))
    """
    return EachStep(list_step, callback)
