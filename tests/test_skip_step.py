"""Tests for joule_heating.utils.skip_step — SIGINT handler utilities."""

import signal
from threading import Event

from joule_heating.utils.skip_step import (
    register_sigint_handler,
    register_sigint_handler_manual,
)


class TestRegisterSigintHandlerManual:
    def test_returns_previous_handler(self):
        original = signal.getsignal(signal.SIGINT)
        event = Event()
        old = register_sigint_handler_manual(event)
        try:
            assert old is original
        finally:
            signal.signal(signal.SIGINT, original)

    def test_sets_event_on_signal(self):
        original = signal.getsignal(signal.SIGINT)
        event = Event()
        register_sigint_handler_manual(event)
        try:
            assert not event.is_set()
            # Simulate SIGINT by calling the handler directly
            handler = signal.getsignal(signal.SIGINT)
            handler(signal.SIGINT, None)
            assert event.is_set()
        finally:
            signal.signal(signal.SIGINT, original)

    def test_custom_handler_used(self):
        original = signal.getsignal(signal.SIGINT)
        event = Event()
        called = []

        def custom(_sig, _frame):
            called.append(True)

        register_sigint_handler_manual(event, custom)
        try:
            handler = signal.getsignal(signal.SIGINT)
            handler(signal.SIGINT, None)
            assert called
            assert not event.is_set()  # Custom handler doesn't set event
        finally:
            signal.signal(signal.SIGINT, original)


class TestRegisterSigintHandlerContext:
    def test_yields_fresh_event(self):
        with register_sigint_handler() as event:
            assert isinstance(event, Event)
            assert not event.is_set()

    def test_restores_handler_on_exit(self):
        original = signal.getsignal(signal.SIGINT)
        with register_sigint_handler():
            pass
        restored = signal.getsignal(signal.SIGINT)
        assert restored is original

    def test_each_call_yields_different_event(self):
        with register_sigint_handler() as e1:
            pass
        with register_sigint_handler() as e2:
            pass
        assert e1 is not e2

    def test_handler_sets_event(self):
        with register_sigint_handler() as event:
            handler = signal.getsignal(signal.SIGINT)
            handler(signal.SIGINT, None)
            assert event.is_set()
