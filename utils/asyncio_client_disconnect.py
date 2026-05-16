"""Quiet benign client disconnect noise on Windows (WinError 10054, etc.)."""

from __future__ import annotations

import asyncio
import logging
import sys

_log = logging.getLogger("usgromana")
_installed = False

_BENIGN = (ConnectionResetError, BrokenPipeError, ConnectionAbortedError)


def install_asyncio_disconnect_quiet_handler() -> None:
    """
    Downgrade asyncio 'connection lost' tracebacks when the remote client closed first.
    Common when refreshing ComfyUI or closing a tab mid-request; not a server bug.
    """
    global _installed
    if _installed or sys.platform != "win32":
        return

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        return

    previous = loop.get_exception_handler()

    def handler(loop: asyncio.AbstractEventLoop, context: dict) -> None:
        exc = context.get("exception")
        if exc is not None and isinstance(exc, _BENIGN):
            _log.debug(
                "Client disconnected (%s): %s",
                type(exc).__name__,
                exc,
            )
            return
        if previous is not None:
            previous(loop, context)
        else:
            loop.default_exception_handler(context)

    loop.set_exception_handler(handler)
    _installed = True
