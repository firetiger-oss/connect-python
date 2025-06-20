from collections.abc import AsyncIterator
from collections.abc import Iterable
from typing import TypeVar

import aiohttp
import urllib3
from google.protobuf.message import Message

from .client_base import AsyncBaseClient
from .client_base import BaseClient
from .headers import HeaderInput
from .streams import AsyncStreamOutput
from .streams import StreamOutput
from .unary import UnaryOutput

T = TypeVar("T", bound=Message)


class ConnectGRPCWebClient(BaseClient):
    def __init__(self, http_client: urllib3.PoolManager):
        raise NotImplementedError

    def call_unary(
        self,
        url: str,
        req: Message,
        response_type: type[T],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> UnaryOutput[T]:
        raise NotImplementedError

    def call_streaming(
        self,
        url: str,
        reqs: Iterable[Message],
        response_type: type[T],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> StreamOutput[T]:
        raise NotImplementedError


class AsyncConnectGRPCWebClient(AsyncBaseClient):
    def __init__(self, http_client: aiohttp.ClientSession):
        raise NotImplementedError

    async def call_unary(
        self,
        url: str,
        req: Message,
        response_type: type[T],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> UnaryOutput[T]:
        raise NotImplementedError

    async def call_streaming(
        self,
        url: str,
        reqs: AsyncIterator[Message],
        response_type: type[T],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> AsyncStreamOutput[T]:
        raise NotImplementedError
