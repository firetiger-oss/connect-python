from collections.abc import AsyncIterator
from collections.abc import Iterator
from typing import Protocol
from typing import TypeVar

from google.protobuf.message import Message

from .headers import HeaderInput
from .streams import StreamOutput
from .unary import UnaryOutput

T = TypeVar("T", bound=Message)


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
    ) -> StreamOutput[T]: ...

class SynchronousBaseClient(Protocol[T]):
    def call_unary_sync(
            self, url: str, req: Message, response_type: type[T], 
            extra_headers: HeaderInput | None = None,
            timeout_seconds: float | None = None,
    ) -> UnaryOutput[T]: ...

    def call_streaming_sync(
        self,
        url: str,
        reqs: Iterator[Message],
        response_type: type[T],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> StreamOutput[T]: ...
