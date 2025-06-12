import aiohttp
from google.protobuf.message import Message
from typing import Type, TypeVar, AsyncIterator
from collections.abc import Iterable

from .client_base import BaseClient
from .streams import StreamInput

T = TypeVar('T', bound=Message)


class ConnectProtobufClient(BaseClient):
    def __init__(self, http_client: aiohttp.ClientSession):
        self._http_client = http_client

    async def call_unary(self, url: str, req: Message, response_type: Type[T]) -> T:
        data = req.SerializeToString()
        headers = {
            "Content-Type": "application/proto",
            "Connect-Protocol-Version": "1",
            "Content-Encoding": "identity",
        }
        async with self._http_client.request("POST", url, data=data) as resp:
            pass

        raise NotImplementedError
            

    async def call_client_streaming(self, url: str, reqs: StreamInput[Message], response_type: Type[T]) -> T:
        raise NotImplementedError

    def call_server_streaming(self, url: str, req: Message, response_type: Type[T]) -> AsyncIterator[T]:
        raise NotImplementedError

    def call_bidirectional_streaming(
        self, url: str, reqs: StreamInput[Message], response_type: Type[T]
    ) -> AsyncIterator[T]:
        raise NotImplementedError
