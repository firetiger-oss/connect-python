from __future__ import annotations

from collections.abc import AsyncIterator
from enum import Enum
from typing import TypeVar

import aiohttp
from google.protobuf.message import Message

from .client_base import BaseClient
from .client_connect import ConnectProtocolClient
from .client_grpc import ConnectGRPCClient
from .client_grpc_web import ConnectGRPCWebClient
from .connect_serialization import CONNECT_JSON_SERIALIZATION
from .connect_serialization import CONNECT_PROTOBUF_SERIALIZATION
from .streams import StreamInput
from .streams import StreamOutput

T = TypeVar("T", bound=Message)


class ConnectProtocol(Enum):
    CONNECT_PROTOBUF = "connect-proto"
    CONNECT_JSON = "connect-json"
    GRPC = "grpc"
    GRPC_WEB = "grpc-web"


class ConnectClient:
    _client: BaseClient

    def __init__(
        self,
        http_client: aiohttp.ClientSession | None = None,
        protocol: ConnectProtocol = ConnectProtocol.CONNECT_PROTOBUF,
    ):
        if http_client is None:
            http_client = aiohttp.ClientSession()

        if protocol == ConnectProtocol.CONNECT_PROTOBUF:
            self._client = ConnectProtocolClient(http_client, CONNECT_PROTOBUF_SERIALIZATION)
        elif protocol == ConnectProtocol.CONNECT_JSON:
            self._client = ConnectProtocolClient(http_client, CONNECT_JSON_SERIALIZATION)
        elif protocol == ConnectProtocol.GRPC:
            self._client = ConnectGRPCClient(http_client)
        elif protocol == ConnectProtocol.GRPC_WEB:
            self._client = ConnectGRPCWebClient(http_client)

    def _to_async_iterator(self, input_stream: StreamInput[T]) -> AsyncIterator[T]:
        """Convert various input types to AsyncIterator"""
        # Check for async iteration first
        if hasattr(input_stream, "__aiter__"):
            return input_stream  # type: ignore[return-value]

        # Fall back to sync iteration (covers lists, iterators, etc.)
        async def _sync_to_async() -> AsyncIterator[T]:
            for item in input_stream:
                yield item

        return _sync_to_async()

    async def call_unary(self, url: str, req: Message, response_type: type[T]) -> T:
        return await self._client.call_unary(url, req, response_type)

    async def call_client_streaming(
        self, url: str, reqs: StreamInput[Message], response_type: type[T]
    ) -> T:
        async_iter = self._to_async_iterator(reqs)
        stream_output = await self._client.call_streaming(url, async_iter, response_type)
        async for response in stream_output:
            return response
        raise RuntimeError("No response received from client streaming call")

    async def call_server_streaming(
        self, url: str, req: Message, response_type: type[T]
    ) -> StreamOutput[T]:
        async def single_req() -> AsyncIterator[Message]:
            yield req

        return await self._client.call_streaming(url, single_req(), response_type)

    async def call_bidirectional_streaming(
        self, url: str, reqs: StreamInput[Message], response_type: type[T]
    ) -> StreamOutput[T]:
        async_iter = self._to_async_iterator(reqs)
        return await self._client.call_streaming(url, async_iter, response_type)
