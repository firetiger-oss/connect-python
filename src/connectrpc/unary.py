from __future__ import annotations

from typing import Protocol
from typing import TypeVar

from google.protobuf.message import Message
from multidict import MultiDict

T = TypeVar("T", bound=Message, covariant=True)


class UnaryOutput(Protocol[T]):
    def message(self) -> T | None: ...

    def response_headers(self) -> MultiDict[str] | None: ...

    def response_trailers(self) -> MultiDict[str] | None: ...
