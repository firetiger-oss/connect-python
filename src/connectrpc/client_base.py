from collections.abc import AsyncIterator
from collections.abc import Iterable
from typing import Protocol
from typing import TypeVar

from google.protobuf.message import Message

from .headers import HeaderInput
from .streams import AsyncStreamOutput
from .streams import StreamOutput
from .unary import UnaryOutput

T = TypeVar("T", bound=Message)


class BaseClient(Protocol):
    def call_unary(
        self,
        url: str,
        req: Message,
        response_type: type[T],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> UnaryOutput[T]: ...

    def call_streaming(
        self,
        url: str,
        reqs: Iterable[Message],
        response_type: type[T],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> StreamOutput[T]: ...


class AsyncBaseClient(Protocol):
    async def call_unary(
        self,
        url: str,
        req: Message,
        response_type: type[T],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> UnaryOutput[T]: ...

    async def call_streaming(
        self,
        url: str,
        reqs: AsyncIterator[Message],
        response_type: type[T],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> AsyncStreamOutput[T]: ...
