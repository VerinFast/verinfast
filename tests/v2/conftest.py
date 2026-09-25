"""Shared fixtures, and the guard that keeps this suite offline.

`N16` says the v2 tests run with no network. That was a README promise until
now: a parser that quietly grew a registry lookup, or a scanner that built a
real client instead of taking an injected one, would have passed CI and only
failed in an air-gapped install — or silently made a customer's scan phone
out.

The guard below turns that into a test failure. It patches the socket layer
rather than any one HTTP client, so it catches `httpx`, `requests`, `urllib`
and anything else equally.

Subprocesses are not covered — `git` and `modernmetric` run in their own
interpreters — but neither of those is supposed to reach the network either,
and both are invoked with explicit arguments a reviewer can read.
"""

from __future__ import annotations

import socket

import pytest


class NetworkUsedInTests(AssertionError):
    """Raised instead of opening a real connection."""


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail any test that tries to open a real connection.

    `httpx.MockTransport` never reaches this — it short-circuits above the
    transport — so the intended way to test a client stays available.
    """

    def blocked(self, address, *args, **kwargs):
        raise NetworkUsedInTests(
            f"this test tried to connect to {address!r}. The v2 suite runs "
            "offline (N16): inject an httpx.MockTransport, or pass a client "
            "with enabled=False."
        )

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda address, *a, **k: blocked(None, address),
    )
