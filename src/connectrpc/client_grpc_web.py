from collections.abc import AsyncIterator
from typing import TypeVar

import aiohttp
from google.protobuf.message import Message

from .client_base import BaseClient
from .headers import HeaderInput
from .streams import StreamOutput
from .unary import UnaryOutput

T = TypeVar("T", bound=Message)


class ConnectGRPCWebClient(BaseClient):
    def __init__(self, http_client: aiohttp.ClientSession):
        raise NotImplementedError

    async def call_unary(
        self,
        url: str,
        req: Message,
        response_type: type[T],
        extra_headers: HeaderInput | None = None,
    ) -> UnaryOutput[T]:
        raise NotImplementedError

    async def call_streaming(
        self,
        url: str,
        reqs: AsyncIterator[Message],
        response_type: type[T],
        extra_headers: HeaderInput | None = None,
    ) -> StreamOutput[T]:
        raise NotImplementedError
