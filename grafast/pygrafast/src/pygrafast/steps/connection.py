"""connection() - Cursor pagination helper for GraphQL connections.

Implements the Relay-style cursor connection spec by wrapping a list step
with pagination (first/after/last/before/offset) and producing a connection
dict with edges, nodes, and pageInfo.
"""

from __future__ import annotations

import base64
from typing import Any, Callable

from ..step import Step
from .access import AccessStep
from .each import each
from .lambda_step import lambda_
from .list_step import list_


def _encode_cursor(index: int) -> str:
    """Encode a numeric index as a base64 cursor."""
    return base64.b64encode(str(index).encode("utf-8")).decode("utf-8")


def _decode_cursor(cursor: str) -> int:
    """Decode a base64 cursor to a numeric index."""
    decoded = base64.b64decode(cursor.encode("utf-8")).decode("utf-8")
    return int(decoded)


def _apply_pagination(args: list[Any]) -> dict[str, Any] | None:
    """Apply cursor pagination to a list.

    Args is [full_list, first, after, last, before, offset].

    Returns a dict with:
      - items: the paginated slice of the original list
      - cursors: base64 cursors for each item (using original indices)
      - pageInfo: {hasNextPage, hasPreviousPage, startCursor, endCursor}
    """
    full_list, first, after, last, before, offset = args

    if full_list is None:
        return None

    # Validate incompatible argument combinations (matching TS behavior)
    if first is not None and before is not None:
        raise ValueError(
            "You must not set both `first` and `before`; specify `first` and "
            "optionally `after` to paginate forwards, or `last` and optionally "
            "`before` to paginate backwards."
        )
    if last is not None and after is not None:
        raise ValueError(
            "You must not set `last` and `after`; specify `first` and "
            "optionally `after` to paginate forwards, or `last` and optionally "
            "`before` to paginate backwards; "
        )
    if first is not None and last is not None:
        raise ValueError(
            "It is not permitted to set both 'first' and 'last' in the same field."
        )

    total = len(full_list)

    # Determine the window of indices into the full list
    start_index = 0
    end_index = total

    # Apply 'after' cursor: skip everything up to and including the cursor position
    if after is not None:
        after_index = _decode_cursor(after)
        start_index = after_index + 1

    # Apply 'before' cursor: only include items before this position
    if before is not None:
        before_index = _decode_cursor(before)
        end_index = min(end_index, before_index)

    # Apply offset
    if offset is not None:
        start_index = start_index + offset

    # Clamp
    start_index = max(0, min(start_index, total))
    end_index = max(start_index, min(end_index, total))

    # Available range after cursor/offset filtering
    available_count = end_index - start_index

    # Apply first/last
    has_previous_page = False
    has_next_page = False

    if first is not None:
        if first < available_count:
            has_next_page = True
            end_index = start_index + first
        # hasPreviousPage is true if we skipped items at the start
        has_previous_page = start_index > 0
    elif last is not None:
        if last < available_count:
            has_previous_page = True
            start_index = end_index - last
        # hasNextPage is true if we cut items at the end
        has_next_page = end_index < total
    else:
        # No first/last limit
        has_previous_page = start_index > 0
        has_next_page = end_index < total

    items = full_list[start_index:end_index]
    cursors = [_encode_cursor(start_index + i) for i in range(len(items))]

    start_cursor = cursors[0] if cursors else None
    end_cursor = cursors[-1] if cursors else None

    return {
        "items": items,
        "cursors": cursors,
        "pageInfo": {
            "hasNextPage": has_next_page,
            "hasPreviousPage": has_previous_page,
            "startCursor": start_cursor,
            "endCursor": end_cursor,
        },
    }


def _extract_items(paginated: dict[str, Any] | None) -> list[Any]:
    """Extract the items list from pagination result."""
    if paginated is None:
        return []
    return paginated.get("items", [])


def _build_connection_dict(args: list[Any]) -> dict[str, Any] | None:
    """Build the final connection dict from resolved nodes and pagination data.

    Args is [resolved_nodes, paginated_data].
    """
    nodes, paginated = args
    if paginated is None:
        return None

    cursors = paginated.get("cursors", [])
    page_info = paginated.get("pageInfo", {})

    # Build edges: each edge has node + cursor
    edges = []
    if nodes is not None:
        for i, node in enumerate(nodes):
            cursor = cursors[i] if i < len(cursors) else None
            edges.append({"node": node, "cursor": cursor})

    return {
        "nodes": nodes if nodes is not None else [],
        "edges": edges,
        "pageInfo": page_info,
    }


def connection(
    list_step: Step[Any],
    field_args: Any,
    node_callback: Callable[[Step[Any]], Step[Any]] | None = None,
) -> Step[Any]:
    """Create a connection step with cursor pagination.

    Args:
        list_step: A step producing the full list of items.
        field_args: The FieldArgs object providing pagination arguments
            (first, after, last, before, offset).
        node_callback: Optional callback to resolve each raw item into
            a node object. Called during planning with an item step.
            If None, raw items are used as nodes directly.

    Returns:
        A step producing a connection dict with edges, nodes, and pageInfo.
    """
    # Get pagination argument steps
    first_step = field_args.get_raw("first")
    after_step = field_args.get_raw("after")
    last_step = field_args.get_raw("last")
    before_step = field_args.get_raw("before")
    offset_step = field_args.get_raw("offset")

    # Apply pagination: produces {items, cursors, pageInfo}
    paginated = lambda_(
        [list_step, first_step, after_step, last_step, before_step, offset_step],
        _apply_pagination,
    )

    # Extract paginated items
    items_step = lambda_(paginated, _extract_items)

    # Resolve nodes through callback if provided
    if node_callback is not None:
        nodes_step = each(items_step, node_callback)
    else:
        nodes_step = items_step

    # Assemble final connection dict
    return lambda_(
        [nodes_step, paginated],
        _build_connection_dict,
    )
