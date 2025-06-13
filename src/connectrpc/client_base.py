from google.protobuf.message import Message
from typing import Protocol, Type, TypeVar, Union, AsyncIterator
from collections.abc import Iterable

from .streams import StreamInput

T = TypeVar("T", bound=Message)


class BaseClient(Protocol):
    async def call_unary(self, url: str, req: Message, response_type: Type[T]) -> T: ...

    def call_streaming(
        self, url: str, reqs: StreamInput[Message], response_type: Type[T]
    ) -> AsyncIterator[T]: ...
