"""OperationPlan - the complete execution plan for a GraphQL operation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from graphql import (
    DocumentNode,
    FieldNode,
    GraphQLEnumType,
    GraphQLField,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLScalarType,
    GraphQLSchema,
    GraphQLUnionType,
    InlineFragmentNode,
    OperationDefinitionNode,
    SelectionSetNode,
    is_abstract_type,
    is_leaf_type,
)
from graphql.language import OperationType
from graphql.utilities import value_from_ast

from ..constants import UNDEFINED
from ..step import Step
from .layer_plan import LayerPlan, LayerPlanReasonRoot
from .output_plan import OutputPlan
from .step_tracker import StepTracker
from .with_global_layer_plan import with_global_layer_plan

if TYPE_CHECKING:
    pass

# Key used to store grafast plan resolver on field extensions
GRAFAST_PLAN_RESOLVER_KEY = "grafast_plan_resolver"
# Key used to store planType on interface/union extensions
GRAFAST_PLAN_TYPE_KEY = "grafast_plan_type"


class FieldArgs:
    """Provides access to field arguments during planning."""

    def __init__(
        self,
        args: dict[str, Step[Any]],
    ) -> None:
        self._args = args

    def get_raw(self, name: str) -> Step[Any]:
        """Get the step for a raw argument value.

        If the argument was not provided in the query, returns a constant
        step producing None (matching the TS behaviour where missing optional
        args yield an undefined/null step).
        """
        if name not in self._args:
            from ..steps.input_static_leaf import InputStaticLeafStep

            # We are inside a plan resolver which is called within
            # with_global_layer_plan, so the context is already set.
            step = InputStaticLeafStep(None)
            # Cache so repeated calls return the same step
            self._args[name] = step
            return step
        return self._args[name]

    def __getattr__(self, name: str) -> Any:
        if name.startswith("$"):
            return self.get_raw(name[1:])
        raise AttributeError(name)


class OperationPlan:
    """The complete plan for a GraphQL operation.

    Created by walking the operation's selection set and calling plan resolvers
    for each field. The result is a DAG of Steps organized into LayerPlans.
    """

    phase: str  # "plan", "optimize", "finalize", "execute"

    def __init__(
        self,
        schema: GraphQLSchema,
        document: DocumentNode,
        operation: OperationDefinitionNode,
        variable_values: dict[str, Any] | None = None,
    ) -> None:
        self.schema = schema
        self.document = document
        self.operation = operation
        self.variable_values = variable_values or {}
        self.step_tracker = StepTracker()
        self.phase = "plan"

        self._layer_plans: list[LayerPlan] = []
        self._output_plan: OutputPlan | None = None

        # Create root layer plan
        self.root_layer_plan = LayerPlan(self, LayerPlanReasonRoot())

        # Plan the operation
        self._plan_operation()

        # Finalize
        self.phase = "finalize"
        self._finalize()
        self.phase = "execute"

    def _add_layer_plan(self, layer_plan: LayerPlan) -> int:
        """Register a layer plan. Returns its id."""
        lp_id = len(self._layer_plans)
        self._layer_plans.append(layer_plan)
        return lp_id

    def _plan_operation(self) -> None:
        """Walk the operation and build the step DAG."""
        op = self.operation
        op_type = op.operation

        if op_type == OperationType.QUERY:
            root_type = self.schema.query_type
        elif op_type == OperationType.MUTATION:
            root_type = self.schema.mutation_type
        elif op_type == OperationType.SUBSCRIPTION:
            root_type = self.schema.subscription_type
        else:
            raise ValueError(f"Unsupported operation type: {op_type}")

        if root_type is None:
            raise ValueError(f"Schema has no {op_type.value} type")

        # Create a __ValueStep for the root value (always empty object)
        from ..steps.value_step import ValueStep

        def make_root() -> ValueStep[Any]:
            return ValueStep()

        root_step = with_global_layer_plan(
            self.root_layer_plan, None, make_root
        )

        # Create the root output plan
        self._output_plan = OutputPlan(self.root_layer_plan, mode="object")

        # Plan each field in the selection set
        assert op.selection_set is not None
        self._plan_selection_set(
            op.selection_set,
            root_type,
            root_step,
            self._output_plan,
            self.root_layer_plan,
        )

    def _plan_selection_set(
        self,
        selection_set: SelectionSetNode,
        parent_type: GraphQLObjectType | GraphQLInterfaceType | GraphQLUnionType,
        parent_step: Step[Any],
        output_plan: OutputPlan,
        layer_plan: LayerPlan,
        concrete_type: GraphQLObjectType | None = None,
    ) -> None:
        """Plan each field in a selection set."""
        for selection in selection_set.selections:
            if isinstance(selection, FieldNode):
                # Use the concrete type for field lookup if available
                field_type = concrete_type or parent_type
                if isinstance(field_type, (GraphQLObjectType, GraphQLInterfaceType)):
                    self._plan_field(
                        selection,
                        field_type,
                        parent_step,
                        output_plan,
                        layer_plan,
                    )
            elif isinstance(selection, InlineFragmentNode):
                self._plan_inline_fragment(
                    selection,
                    parent_type,
                    parent_step,
                    output_plan,
                    layer_plan,
                )

    def _plan_inline_fragment(
        self,
        fragment: InlineFragmentNode,
        parent_type: GraphQLObjectType | GraphQLInterfaceType | GraphQLUnionType,
        parent_step: Step[Any],
        output_plan: OutputPlan,
        layer_plan: LayerPlan,
    ) -> None:
        """Plan an inline fragment (... on TypeName { ... })."""
        if fragment.type_condition is None:
            # No type condition — applies to current type
            if fragment.selection_set:
                self._plan_selection_set(
                    fragment.selection_set,
                    parent_type,
                    parent_step,
                    output_plan,
                    layer_plan,
                )
            return

        type_name = fragment.type_condition.name.value
        target_type = self.schema.type_map.get(type_name)
        if target_type is None:
            return

        if not isinstance(target_type, (GraphQLObjectType, GraphQLInterfaceType)):
            return

        # For polymorphic output plans, record which type this fragment applies to
        if output_plan.mode == "polymorphic":
            # Add fields to the type-specific section
            if type_name not in output_plan.type_plans:
                output_plan.type_plans[type_name] = ([], target_type)

            if fragment.selection_set:
                for sel in fragment.selection_set.selections:
                    if isinstance(sel, FieldNode):
                        self._plan_field(
                            sel,
                            target_type,
                            parent_step,
                            output_plan,
                            layer_plan,
                            type_condition=type_name,
                        )
                    elif isinstance(sel, InlineFragmentNode):
                        self._plan_inline_fragment(
                            sel,
                            target_type,
                            parent_step,
                            output_plan,
                            layer_plan,
                        )
        else:
            # Non-polymorphic context — just plan the fields
            if fragment.selection_set:
                concrete = target_type if isinstance(target_type, GraphQLObjectType) else None
                self._plan_selection_set(
                    fragment.selection_set,
                    target_type,
                    parent_step,
                    output_plan,
                    layer_plan,
                    concrete_type=concrete,
                )

    def _plan_field(
        self,
        field_node: FieldNode,
        parent_type: GraphQLObjectType | GraphQLInterfaceType,
        parent_step: Step[Any],
        output_plan: OutputPlan,
        layer_plan: LayerPlan,
        type_condition: str | None = None,
    ) -> None:
        """Plan a single field."""
        field_name = field_node.name.value
        response_key = (
            field_node.alias.value if field_node.alias else field_name
        )

        # Get the field definition from the schema
        fields = parent_type.fields
        if field_name not in fields:
            # Introspection fields like __typename
            if field_name == "__typename":
                # In polymorphic context, __typename is resolved dynamically
                if output_plan.mode == "polymorphic" and output_plan.typename_step is not None:
                    child_output = OutputPlan(layer_plan, mode="leaf")
                    child_output.root_step = output_plan.typename_step
                    if type_condition is not None:
                        if type_condition not in output_plan.type_children:
                            output_plan.type_children[type_condition] = {}
                            output_plan.type_keys[type_condition] = []
                        output_plan.type_children[type_condition][response_key] = (child_output, output_plan.typename_step)
                        output_plan.type_keys[type_condition].append(response_key)
                    else:
                        output_plan.children[response_key] = (child_output, output_plan.typename_step)
                        if response_key not in output_plan.keys:
                            output_plan.keys.append(response_key)
                    return

                from ..steps.constant import ConstantStep

                def make_typename() -> ConstantStep[str]:
                    return ConstantStep(parent_type.name)

                typename_step = with_global_layer_plan(
                    layer_plan, None, make_typename
                )
                child_output = OutputPlan(layer_plan, mode="leaf")
                child_output.root_step = typename_step
                if type_condition is not None:
                    if type_condition not in output_plan.type_children:
                        output_plan.type_children[type_condition] = {}
                        output_plan.type_keys[type_condition] = []
                    output_plan.type_children[type_condition][response_key] = (child_output, typename_step)
                    output_plan.type_keys[type_condition].append(response_key)
                else:
                    output_plan.children[response_key] = (child_output, typename_step)
                    if response_key not in output_plan.keys:
                        output_plan.keys.append(response_key)
                return
            return  # Skip unknown fields

        field_def = fields[field_name]
        field_type = field_def.type

        # Build argument steps
        arg_steps = self._build_arg_steps(field_node, field_def, layer_plan)
        field_args = FieldArgs(arg_steps)

        # Call the plan resolver
        plan_resolver = self._get_plan_resolver(parent_type.name, field_name, field_def)
        if plan_resolver is not None:
            def call_resolver() -> Step[Any]:
                return plan_resolver(parent_step, field_args)

            result_step = with_global_layer_plan(
                layer_plan, None, call_resolver
            )
        else:
            # No plan resolver — use an AccessStep as default
            from ..steps.access import AccessStep

            def make_access() -> Step[Any]:
                return AccessStep(parent_step, [field_name])

            result_step = with_global_layer_plan(
                layer_plan, None, make_access
            )

        # Unwrap NonNull for type analysis
        unwrapped_type = field_type
        while isinstance(unwrapped_type, GraphQLNonNull):
            unwrapped_type = unwrapped_type.of_type

        # Handle list types: unwrap [Type] -> Type
        is_list = False
        if isinstance(unwrapped_type, GraphQLList):
            is_list = True
            unwrapped_type = unwrapped_type.of_type
            # Further unwrap NonNull inside the list
            while isinstance(unwrapped_type, GraphQLNonNull):
                unwrapped_type = unwrapped_type.of_type

        # Determine output mode based on the field's return type
        if is_list:
            # Array output mode
            child_output = OutputPlan(layer_plan, mode="array")
            child_output.root_step = result_step

            # Create the element output plan
            if is_leaf_type(unwrapped_type):
                elem_output = OutputPlan(layer_plan, mode="leaf")
                if isinstance(unwrapped_type, GraphQLScalarType):
                    elem_output.serializer = unwrapped_type.serialize
                elif isinstance(unwrapped_type, GraphQLEnumType):
                    elem_output.serializer = unwrapped_type.serialize
            elif isinstance(unwrapped_type, GraphQLObjectType):
                elem_output = OutputPlan(layer_plan, mode="object")
                if field_node.selection_set:
                    self._plan_selection_set(
                        field_node.selection_set,
                        unwrapped_type,
                        result_step,
                        elem_output,
                        layer_plan,
                    )
            elif is_abstract_type(unwrapped_type):
                elem_output = OutputPlan(layer_plan, mode="polymorphic")
                plan_type_fn = self._get_plan_type(unwrapped_type)
                if plan_type_fn is not None:
                    def call_plan_type_list() -> Step[Any]:
                        plan_result = plan_type_fn(result_step)
                        if isinstance(plan_result, dict):
                            typename_step = plan_result.get("$__typename")
                            elem_output.typename_step = typename_step
                            plan_for_type = plan_result.get("planForType")
                            if plan_for_type is not None:
                                elem_output.plan_for_type = plan_for_type
                            return typename_step
                        return None  # type: ignore
                    with_global_layer_plan(layer_plan, None, call_plan_type_list)
                if field_node.selection_set:
                    self._plan_selection_set(
                        field_node.selection_set,
                        unwrapped_type,
                        result_step,
                        elem_output,
                        layer_plan,
                    )
            else:
                elem_output = OutputPlan(layer_plan, mode="leaf")

            child_output.element_output = elem_output

        elif is_leaf_type(unwrapped_type):
            child_output = OutputPlan(layer_plan, mode="leaf")
            child_output.root_step = result_step
            # Get serializer for scalar types
            if isinstance(unwrapped_type, GraphQLScalarType):
                child_output.serializer = unwrapped_type.serialize
            elif isinstance(unwrapped_type, GraphQLEnumType):
                child_output.serializer = unwrapped_type.serialize
            child_output.type_name = unwrapped_type.name
        elif isinstance(unwrapped_type, GraphQLObjectType):
            child_output = OutputPlan(layer_plan, mode="object")
            child_output.root_step = result_step
            if field_node.selection_set:
                self._plan_selection_set(
                    field_node.selection_set,
                    unwrapped_type,
                    result_step,
                    child_output,
                    layer_plan,
                )
        elif is_abstract_type(unwrapped_type):
            # Interface or Union type — use polymorphic output
            child_output = OutputPlan(layer_plan, mode="polymorphic")
            child_output.root_step = result_step

            # Get the planType function from schema extensions
            plan_type_fn = self._get_plan_type(unwrapped_type)
            if plan_type_fn is not None:
                # Call planType to get the __typename step
                def call_plan_type() -> Step[Any]:
                    plan_result = plan_type_fn(result_step)
                    if isinstance(plan_result, dict):
                        typename_step = plan_result.get("$__typename")
                        child_output.typename_step = typename_step
                        # Store planForType if provided
                        plan_for_type = plan_result.get("planForType")
                        if plan_for_type is not None:
                            child_output.plan_for_type = plan_for_type
                        return typename_step
                    return None  # type: ignore

                with_global_layer_plan(layer_plan, None, call_plan_type)

            if field_node.selection_set:
                self._plan_selection_set(
                    field_node.selection_set,
                    unwrapped_type,
                    result_step,
                    child_output,
                    layer_plan,
                )
        else:
            # Fallback: treat as leaf
            child_output = OutputPlan(layer_plan, mode="leaf")
            child_output.root_step = result_step

        # Record in parent output plan
        if type_condition is not None:
            # Field belongs to a specific polymorphic type
            if type_condition not in output_plan.type_children:
                output_plan.type_children[type_condition] = {}
                output_plan.type_keys[type_condition] = []
            output_plan.type_children[type_condition][response_key] = (child_output, result_step)
            output_plan.type_keys[type_condition].append(response_key)
        else:
            output_plan.children[response_key] = (child_output, result_step)
            if response_key not in output_plan.keys:
                output_plan.keys.append(response_key)

    def _build_arg_steps(
        self,
        field_node: FieldNode,
        field_def: GraphQLField,
        layer_plan: LayerPlan,
    ) -> dict[str, Step[Any]]:
        """Build Step objects for each argument."""
        arg_steps: dict[str, Step[Any]] = {}
        arg_defs = field_def.args

        for arg_name, arg_def in arg_defs.items():
            # Find the argument value in the field node
            arg_value_node = None
            if field_node.arguments:
                for arg_node in field_node.arguments:
                    if arg_node.name.value == arg_name:
                        arg_value_node = arg_node.value
                        break

            if arg_value_node is not None:
                # Check if this is a variable reference
                from graphql.language import VariableNode

                if isinstance(arg_value_node, VariableNode):
                    var_name = arg_value_node.name.value
                    # Create a step that will resolve to the variable value at execution time
                    from ..steps.input_static_leaf import InputStaticLeafStep

                    var_value = self.variable_values.get(var_name, UNDEFINED)
                    if var_value is not UNDEFINED:
                        def make_var_step(val: Any = var_value) -> InputStaticLeafStep:
                            return InputStaticLeafStep(val)

                        step = with_global_layer_plan(
                            layer_plan, None, make_var_step
                        )
                    else:
                        # Use default value if available
                        default = arg_def.default_value
                        def make_default_step(val: Any = default) -> InputStaticLeafStep:
                            return InputStaticLeafStep(val)

                        step = with_global_layer_plan(
                            layer_plan, None, make_default_step
                        )
                else:
                    # Literal value — coerce it
                    coerced = value_from_ast(arg_value_node, arg_def.type)
                    from ..steps.input_static_leaf import InputStaticLeafStep

                    def make_literal_step(val: Any = coerced) -> InputStaticLeafStep:
                        return InputStaticLeafStep(val)

                    step = with_global_layer_plan(
                        layer_plan, None, make_literal_step
                    )

                arg_steps[arg_name] = step

        return arg_steps

    def _get_plan_resolver(
        self,
        type_name: str,
        field_name: str,
        field_def: GraphQLField,
    ) -> Callable[..., Step[Any]] | None:
        """Get the plan resolver for a field, if any."""
        # Check field extensions for grafast plan resolver
        extensions = field_def.extensions
        if extensions and GRAFAST_PLAN_RESOLVER_KEY in extensions:
            return extensions[GRAFAST_PLAN_RESOLVER_KEY]
        return None

    def _get_plan_type(
        self,
        abstract_type: GraphQLInterfaceType | GraphQLUnionType,
    ) -> Callable[..., Any] | None:
        """Get the planType function for an interface or union type."""
        extensions = abstract_type.extensions
        if extensions and GRAFAST_PLAN_TYPE_KEY in extensions:
            return extensions[GRAFAST_PLAN_TYPE_KEY]
        return None

    def _finalize(self) -> None:
        """Finalize the plan — build execution phases."""
        # Finalize all steps
        for step in self.step_tracker.all_steps():
            if not step.is_finalized:
                step.finalize()

        # Build phases for each layer plan
        for lp in self._layer_plans:
            lp.finalize()
