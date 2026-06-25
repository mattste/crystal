"""Middleware system for pygrafast.

Provides a way to intercept and modify the behavior of various phases
in the grafast execution pipeline (parse, validate, plan, execute).

Middleware follows a standard next-function pattern: each middleware
receives the event data and a ``next`` callable. Calling ``next()``
invokes the next middleware in the chain (or the default behavior if
there are no more middlewares). Middleware can modify event data before
calling ``next()``, inspect/modify the result after, or skip ``next()``
entirely to short-circuit the phase.

For phases that involve async operations (like ``execute``), middleware
callbacks should be ``async def`` functions and should ``await next()``.
For purely synchronous phases (like ``parseAndValidate``), plain
synchronous callbacks work fine.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Union


@dataclass
class MiddlewareEvent:
    """Data passed to a middleware callback.

    Attributes:
        phase: The name of the phase being intercepted.
        args: A mutable dict of arguments relevant to the phase.
              Middleware can read/modify these before calling ``next()``.
    """

    phase: str
    args: dict[str, Any] = field(default_factory=dict)


# A middleware callback: receives (event, next_fn) and returns a result.
# For async phases the callback and next_fn are both async.
MiddlewareCallback = Callable[[MiddlewareEvent, Callable[[], Any]], Any]


class Middleware:
    """A collection of phase-keyed middleware callbacks.

    Usage::

        mw = Middleware()
        mw.register("execute", my_execute_middleware)

    Or construct from a dict::

        mw = Middleware.from_dict({
            "execute": my_execute_middleware,
            "parseAndValidate": my_parse_middleware,
        })

    For synchronous phases (parseAndValidate, establishOperationPlan)::

        def my_middleware(event, next):
            # modify event.args if desired
            result = next()
            # inspect / modify result
            return result

    For async phases (execute)::

        async def my_middleware(event, next):
            # modify event.args if desired
            result = await next()
            # inspect / modify result
            return result
    """

    def __init__(self) -> None:
        self._callbacks: dict[str, list[MiddlewareCallback]] = {}

    @classmethod
    def from_dict(
        cls,
        callbacks: dict[str, MiddlewareCallback | list[MiddlewareCallback]],
    ) -> Middleware:
        """Create a Middleware instance from a dict of phase -> callback(s)."""
        mw = cls()
        for phase, cb in callbacks.items():
            if isinstance(cb, list):
                for c in cb:
                    mw.register(phase, c)
            else:
                mw.register(phase, cb)
        return mw

    def register(self, phase: str, callback: MiddlewareCallback) -> None:
        """Register a middleware callback for a phase."""
        self._callbacks.setdefault(phase, []).append(callback)

    def run(self, phase: str, args: dict[str, Any], default: Callable[[], Any]) -> Any:
        """Run the middleware chain for *phase*, falling through to *default*.

        This is the synchronous variant.  All callbacks and *default* must be
        synchronous functions.

        Parameters:
            phase: The name of the phase (e.g. "parseAndValidate").
            args: A mutable dict of arguments for this phase.
            default: The function to call if no middleware intercepts.

        Returns:
            The value returned by the outermost middleware (or *default*).
        """
        callbacks = self._callbacks.get(phase, [])
        if not callbacks:
            return default()

        event = MiddlewareEvent(phase=phase, args=args)

        def build_chain(index: int) -> Callable[[], Any]:
            if index >= len(callbacks):
                return default

            def next_fn() -> Any:
                return callbacks[index](event, build_chain(index + 1))

            return next_fn

        return callbacks[0](event, build_chain(1))

    async def run_async(
        self, phase: str, args: dict[str, Any], default: Callable[[], Any]
    ) -> Any:
        """Run the middleware chain for *phase* with async support.

        Both the middleware callbacks and *default* may be async (coroutine)
        functions.  If a callback or *default* returns a coroutine it will
        be awaited automatically.

        Middleware callbacks for async phases should be ``async def`` and
        should ``await next()`` to invoke the next layer.

        Parameters:
            phase: The name of the phase (e.g. "execute").
            args: A mutable dict of arguments for this phase.
            default: The (possibly async) function to call at the end.

        Returns:
            The value returned by the outermost middleware (or *default*).
        """
        callbacks = self._callbacks.get(phase, [])

        async def _maybe_await(val: Any) -> Any:
            if asyncio.iscoroutine(val) or asyncio.isfuture(val):
                return await val
            return val

        if not callbacks:
            return await _maybe_await(default())

        event = MiddlewareEvent(phase=phase, args=args)

        def build_chain(index: int) -> Callable[[], Any]:
            if index >= len(callbacks):
                # Wrap default so it returns a coroutine that can be awaited
                async def _awaitable_default() -> Any:
                    return await _maybe_await(default())
                return _awaitable_default

            async def next_fn() -> Any:
                result = callbacks[index](event, build_chain(index + 1))
                return await _maybe_await(result)

            return next_fn

        result = callbacks[0](event, build_chain(1))
        return await _maybe_await(result)
