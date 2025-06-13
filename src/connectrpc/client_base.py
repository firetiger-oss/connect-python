from collections.abc import AsyncIterator
from typing import Protocol
from typing import TypeVar

from google.protobuf.message import Message

from .streams import StreamOutput

T = TypeVar("T", bound=Message)


class BaseClient(Protocol):
    async def call_unary(self, url: str, req: Message, response_type: type[T]) -> T: ...

    async def call_streaming(
        self, url: str, reqs: AsyncIterator[Message], response_type: type[T]
    ) -> StreamOutput[T]: ...
