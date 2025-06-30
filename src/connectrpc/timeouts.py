from __future__ import annotations

import sys
import time
from typing import TYPE_CHECKING

from .errors import ConnectError
from .errors import ConnectErrorCode

if TYPE_CHECKING:
    # wsgiref.types was added in Python 3.11.
    if sys.version_info >= (3, 11):
        pass
    else:
        pass


class ConnectTimeout:
    """
    Represents a client-requested timeout on the RPC operation.
    """

    def __init__(self, timeout_ms: int | None):
        self.start = time.monotonic()
        self.timeout_ms = timeout_ms

    def __str__(self) -> str:
        return f"ConnectTimeout(timeout_ms={self.timeout_ms})"

    def expired(self) -> bool:
        """Returns True if the timeout has been exceeded"""
        if self.timeout_ms is None:
            return False
        elapsed = time.monotonic() - self.start
        return elapsed > self.timeout_ms / 1000.0

    def check(self) -> None:
        """
        Check if the timeout has expired. If it has, raise a ConnectError.
        """
        if self.expired():
            elapsed = time.monotonic() - self.start
            raise ConnectError(
                ConnectErrorCode.DEADLINE_EXCEEDED,
                f"deadline of {self.timeout_ms}ms was exceeded ({int(elapsed * 1000)}ms elapsed)",
            )
