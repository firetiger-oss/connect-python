import aiohttp
from google.protobuf.message import Message
from typing import Type, TypeVar, AsyncIterator
from collections.abc import Iterable

from .client_base import BaseClient
from .streams import StreamInput

T = TypeVar('T', bound=Message)


class ConnectGRPCClient(BaseClient):
    def __init__(self, http_client: aiohttp.ClientSession):
        raise NotImplementedError

    async def call_unary(self, url: str, req: Message, response_type: Type[T]) -> T:
        raise NotImplementedError

    async def call_client_streaming(self, url: str, reqs: StreamInput[Message], response_type: Type[T]) -> T:
        raise NotImplementedError

    async def call_server_streaming(self, url: str, req: Message, response_type: Type[T]) -> AsyncIterator[T]:
        raise NotImplementedError

    async def call_bidirectional_streaming(
        self, url: str, reqs: StreamInput[Message], response_type: Type[T]
    ) -> AsyncIterator[T]:
        raise NotImplementedError
