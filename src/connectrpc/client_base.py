from google.protobuf.message import Message
from typing import Protocol, Type, TypeVar, Union, AsyncIterator
from collections.abc import Iterable

from .streams import StreamInput

T = TypeVar('T', bound=Message)


class BaseClient(Protocol):
    async def call_unary(self, url: str, req: Message, response_type: Type[T]) -> T: ...

    async def call_client_streaming(self, url: str, reqs: StreamInput[Message], response_type: Type[T]) -> T: ...

    async def call_server_streaming(self, url: str, req: Message, response_type: Type[T]) -> AsyncIterator[T]: ...

    async def call_bidirectional_streaming(
        self, url: str, reqs: StreamInput[Message], response_type: Type[T]
    ) -> AsyncIterator[T]: ...
