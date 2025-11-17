"""Centralized signal handling for Joule Heating experiments.

This module provides utilities to manage SIGINT (Ctrl+C) interrupts across
multiple scripts using a shared threading.Event. Instead of each script
managing its own signal handler, use the context manager or register
the handler directly from `__main__`.

Key features:
- Module-level `stop_event` shared across all scripts using this module.
- SIGINT handler that sets the event, allowing loops to check and respond.
- Context manager for automatic registration and restoration of handlers.
- Supports custom handlers for flexibility.

Usage:
=====
1. **Using the context manager** (recommended):
    ```python
    from signal_utils import register_sigint_handler, stop_event

    if __name__ == "__main__":
        with register_sigint_handler():
            run_experiment()
    ```

2. **Manual registration** (for scripts that need more control):
    ```python
    from signal_utils import register_sigint_handler_manual, stop_event
    import signal

    if __name__ == "__main__":
        register_sigint_handler_manual()
        try:
            run_experiment()
        finally:
            signal.signal(signal.SIGINT, signal.default_int_handler)
    ```

Author       : Delwin Tanto
Last updated : 17 Nov 2025
"""

import signal
from threading import Event
from contextlib import contextmanager
from typing import Callable, Optional


# Module-level event set by SIGINT handler to request skipping current step / ending cooldown
stop_event = Event()


def _default_handler(_sig, _frame):
    """Default SIGINT handler: sets the stop flag.

    Handler signature must accept (signum, frame). Args are prefixed with
    underscores to indicate they are intentionally unused.

    Args:
        _sig: Signal number (passed by signal module).
        _frame: Current stack frame (passed by signal module).
    """
    stop_event.set()


def register_sigint_handler_manual(handler: Optional[Callable] = None) -> Callable:
    """Register a SIGINT handler.

    This function installs a signal handler that will be called when Ctrl+C
    is pressed. Use this inside `__main__` if you prefer manual control
    over registration and restoration. For automatic cleanup, prefer
    :func:`register_sigint_handler` context manager instead.

    Args:
        handler: Callable with signature ``handler(signum, frame)``. If ``None``,
            uses the default handler which sets :data:`stop_event`.

    Returns:
        Callable: The original/previous signal handler so you can restore it later.

    Example:
        ```python
        if __name__ == "__main__":
            old_handler = register_sigint_handler_manual()
            try:
                run_experiment()
            finally:
                signal.signal(signal.SIGINT, old_handler)
        ```
    """
    if handler is None:
        handler = _default_handler
    old_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, handler)
    return old_handler


@contextmanager
def register_sigint_handler(handler: Optional[Callable] = None):
    """Context manager for automatic SIGINT handler registration and restoration.

    Registers a signal handler on entry and restores the original handler on exit.
    This is the recommended way to manage signal handlers in scripts with a clear
    entry/exit point (e.g., inside `if __name__ == "__main__":`).

    Args:
        handler: Callable with signature ``handler(signum, frame)``. If ``None``,
            uses the default handler which sets :data:`stop_event`.

    Yields:
        None

    Example:
        ```python
        from signal_utils import register_sigint_handler, stop_event

        if __name__ == "__main__":
            with register_sigint_handler():
                # Ctrl+C will set stop_event
                while True:
                    if stop_event.is_set():
                        stop_event.clear()
                        print("Stopping...")
                        break
        ```
    """
    if handler is None:
        handler = _default_handler
    old_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, handler)
    try:
        yield
    finally:
        try:
            signal.signal(signal.SIGINT, old_handler)
        except (ValueError, OSError):
            # If restoring the handler fails for any reason during shutdown, ignore
            pass
