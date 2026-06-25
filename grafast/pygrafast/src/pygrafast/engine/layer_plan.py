"""LayerPlan - represents an execution boundary / bucket scope."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from ..step import Step
    from .operation_plan import OperationPlan


@dataclass
class LayerPlanReasonRoot:
    type: Literal["root"] = "root"


@dataclass
class LayerPlanReasonListItem:
    type: Literal["listItem"] = "listItem"
    parent_step: Step[Any] | None = None


@dataclass
class LayerPlanReasonPolymorphic:
    type: Literal["polymorphic"] = "polymorphic"
    parent_step: Step[Any] | None = None


@dataclass
class LayerPlanReasonSubroutine:
    type: Literal["subroutine"] = "subroutine"
    parent_step: Step[Any] | None = None


LayerPlanReason = (
    LayerPlanReasonRoot
    | LayerPlanReasonListItem
    | LayerPlanReasonPolymorphic
    | LayerPlanReasonSubroutine
)


class LayerPlan:
    """Represents a bucket/execution scope within the operation plan."""

    id: int
    reason: LayerPlanReason
    operation_plan: OperationPlan
    parent_layer_plan: LayerPlan | None
    children: list[LayerPlan]
    steps: list[Step[Any]]
    root_step: Step[Any] | None
    latest_side_effect_step: Step[Any] | None
    _step_count: int
    # Phases for execution: list of lists of steps in execution order
    phases: list[list[Step[Any]]]

    def __init__(
        self,
        operation_plan: OperationPlan,
        reason: LayerPlanReason,
        parent_layer_plan: LayerPlan | None = None,
    ) -> None:
        self.operation_plan = operation_plan
        self.reason = reason
        self.parent_layer_plan = parent_layer_plan
        self.children = []
        self.steps = []
        self.root_step = None
        self.latest_side_effect_step = None
        self._step_count = 0
        self.phases = []
        self.id = operation_plan._add_layer_plan(self)
        if parent_layer_plan is not None:
            parent_layer_plan.children.append(self)

    def _add_step(self, step: Step[Any]) -> int:
        """Register a step with this layer plan. Returns the step's global id."""
        step_id = self.operation_plan.step_tracker.add_step(step)
        self.steps.append(step)
        self._step_count += 1
        return step_id

    def finalize(self) -> None:
        """Build execution phases from the registered steps.

        Side-effect steps are placed in their own dedicated phases so they
        execute sequentially.  Non-side-effect steps are grouped into
        phases around the side-effect boundaries.
        """
        executable = [s for s in self.steps if not getattr(s, "_no_exec", False)]
        if not executable:
            self.phases = []
            return

        # Check if any step has side effects
        has_any_side_effects = any(
            getattr(s, "has_side_effects", False) for s in executable
        )

        if not has_any_side_effects:
            # No side effects — single phase as before
            self.phases = [executable]
            return

        # Build phases: side-effect steps get their own phase,
        # consecutive non-side-effect steps are grouped together.
        phases: list[list[Step[Any]]] = []
        current_group: list[Step[Any]] = []

        for step in executable:
            if getattr(step, "has_side_effects", False):
                # Flush any accumulated non-side-effect steps
                if current_group:
                    phases.append(current_group)
                    current_group = []
                # Side-effect step gets its own phase
                phases.append([step])
            else:
                current_group.append(step)

        # Flush remaining non-side-effect steps
        if current_group:
            phases.append(current_group)

        self.phases = phases
