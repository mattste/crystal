"""OutputPlan - describes how to serialize execution results into GraphQL response."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Literal

if TYPE_CHECKING:
    from ..step import Step
    from .layer_plan import LayerPlan


class OutputPlan:
    """Describes how to extract a value from the bucket store for the response."""

    def __init__(
        self,
        layer_plan: LayerPlan,
        mode: Literal["root", "object", "leaf", "null", "array", "polymorphic"] = "leaf",
    ) -> None:
        self.layer_plan = layer_plan
        self.mode = mode
        # The step whose output this plan reads
        self.root_step: Step[Any] | None = None
        # For object mode: field_name -> (output_plan, step)
        self.children: dict[str, tuple[OutputPlan, Step[Any] | None]] = {}
        # For object mode: the response key -> field alias
        self.keys: list[str] = []
        # The type (for leaf serialization)
        self.type_name: str | None = None
        # Serializer function for leaf types
        self.serializer: Any = None

        # For polymorphic mode:
        # The step that resolves to __typename
        self.typename_step: Step[Any] | None = None
        # planForType function
        self.plan_for_type: Callable[..., Any] | None = None
        # type-specific children: type_name -> {field_key: (output_plan, step)}
        self.type_children: dict[str, dict[str, tuple[OutputPlan, Step[Any] | None]]] = {}
        # type-specific keys: type_name -> [field_key, ...]
        self.type_keys: dict[str, list[str]] = {}
        # type plans: type_name -> (keys_list, type_obj)
        self.type_plans: dict[str, tuple[list[str], Any]] = {}

        # type-specific root steps: type_name -> Step
        # These come from planForType and hold the loaded data for each concrete type
        self.type_steps: dict[str, Step[Any]] = {}

        # Types for which planForType explicitly returned None (should render as null)
        self.null_types: set[str] = set()

        # For array mode: the output plan for each element
        self.element_output: OutputPlan | None = None
