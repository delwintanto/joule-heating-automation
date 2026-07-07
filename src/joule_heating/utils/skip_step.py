"""Centralized signal handling for Joule Heating experiments.

This module provides utilities to manage SIGINT (Ctrl+C) interrupts across
multiple scripts using a threading.Event. Instead of each script managing
its own signal handler, use the context manager which creates and yields
a fresh Event per invocation.

Key features:
- Context manager that creates +  yields a per-run ``stop_event``.
- SIGINT handler that sets the event, allowing loops to check and respond.
- Automatic registration and restoration of signal handlers.
- Supports custom handlers for flexibility.

Usage:
=====
1. **Using the context manager** (recommended):
    ```python
    from joule_heating.utils.skip_step import register_sigint_handler

    if __name__ == "__main__":
        with register_sigint_handler() as stop_event:
            run_experiment(stop_event=stop_event)
    ```

2. **Manual registration** (for scripts that need more control):
    ```python
    from joule_heating.utils.skip_step import register_sigint_handler_manual
    from threading import Event
    import signal

    if __name__ == "__main__":
        stop_event = Event()
        old = register_sigint_handler_manual(stop_event)
        try:
            run_experiment(stop_event=stop_event)
        finally:
            signal.signal(signal.SIGINT, old)
    ```
"""

import contextlib
import signal
from collections.abc import Callable
from contextlib import contextmanager
from threading import Event


def register_sigint_handler_manual(
    stop_event: Event,
    handler: Callable | None = None,
) -> Callable:
    """Register a SIGINT handler that sets *stop_event*.

    Args:
        stop_event: The ``Event`` that the handler will ``.set()`` on Ctrl+C.
        handler: Callable with signature ``handler(signum, frame)``. If ``None``,
            a default handler that calls ``stop_event.set()`` is used.

    Returns:
        Callable: The previous signal handler so you can restore it later.
    """
    if handler is None:

        def handler(_sig, _frame):
            stop_event.set()

    old_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, handler)
    return old_handler


@contextmanager
def register_sigint_handler(handler: Callable | None = None):
    """Context manager for automatic SIGINT handler registration and restoration.

    Creates a fresh ``threading.Event``, registers a signal handler that sets it
    on Ctrl+C, and yields the event. The original signal handler is restored on exit.

    Args:
        handler: Callable with signature ``handler(signum, frame)``. If ``None``,
            a default handler that sets the yielded event is used.

    Yields:
        Event: A fresh ``threading.Event`` that the SIGINT handler will ``.set()``.
    """
    stop_event = Event()
    if handler is None:

        def handler(_sig, _frame):
            stop_event.set()

    old_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, handler)
    try:
        yield stop_event
    finally:
        with contextlib.suppress(ValueError, OSError):
            signal.signal(signal.SIGINT, old_handler)
