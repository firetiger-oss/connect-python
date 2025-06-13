from collections.abc import AsyncIterator
from typing import TypeVar

import aiohttp
from google.protobuf.message import Message

from .client_base import BaseClient
from .streams import StreamOutput

T = TypeVar("T", bound=Message)


class ConnectGRPCClient(BaseClient):
    def __init__(self, http_client: aiohttp.ClientSession):
        raise NotImplementedError

    async def call_unary(self, url: str, req: Message, response_type: type[T]) -> T:
        raise NotImplementedError

    async def call_streaming(
        self, url: str, reqs: AsyncIterator[Message], response_type: type[T]
    ) -> StreamOutput[T]:
        raise NotImplementedError
