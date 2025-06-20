from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TypeVar

import aiohttp
from google.protobuf.message import Message

from .client_base import AsyncBaseClient
from .client_connect import AsyncConnectProtocolClient
from .client_grpc import AsyncConnectGRPCClient
from .client_grpc_web import AsyncConnectGRPCWebClient
from .client_protocol import ConnectProtocol
from .connect_serialization import CONNECT_JSON_SERIALIZATION
from .connect_serialization import CONNECT_PROTOBUF_SERIALIZATION
from .debugprint import debug
from .headers import HeaderInput
from .streams import AsyncStreamOutput
from .streams import StreamInput
from .unary import ClientStreamingOutput
from .unary import UnaryOutput

T = TypeVar("T", bound=Message)


class AsyncConnectClient:
    _client: AsyncBaseClient

    def __init__(
        self,
        http_client: aiohttp.ClientSession,
        protocol: ConnectProtocol = ConnectProtocol.CONNECT_PROTOBUF,
    ):
        if protocol == ConnectProtocol.CONNECT_PROTOBUF:
            self._client = AsyncConnectProtocolClient(http_client, CONNECT_PROTOBUF_SERIALIZATION)
        elif protocol == ConnectProtocol.CONNECT_JSON:
            self._client = AsyncConnectProtocolClient(http_client, CONNECT_JSON_SERIALIZATION)
        elif protocol == ConnectProtocol.GRPC:
            self._client = AsyncConnectGRPCClient(http_client)
        elif protocol == ConnectProtocol.GRPC_WEB:
            self._client = AsyncConnectGRPCWebClient(http_client)

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

    async def call_unary(
        self,
        url: str,
        req: Message,
        response_type: type[T],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> UnaryOutput[T]:
        debug("AsyncConnectClient.call_unary timeout=", timeout_seconds)
        debug("AsyncConnectClient._client=", self._client)
        return await self._client.call_unary(
            url, req, response_type, extra_headers=extra_headers, timeout_seconds=timeout_seconds
        )

    async def call_client_streaming(
        self,
        url: str,
        reqs: StreamInput[Message],
        response_type: type[T],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> ClientStreamingOutput[T]:
        async_iter = self._to_async_iterator(reqs)
        stream_output = await self._client.call_streaming(
            url,
            async_iter,
            response_type,
            extra_headers=extra_headers,
            timeout_seconds=timeout_seconds,
        )
        return await ClientStreamingOutput.from_async_stream_output(stream_output)

    async def call_server_streaming(
        self,
        url: str,
        req: Message,
        response_type: type[T],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> AsyncStreamOutput[T]:
        async def single_req() -> AsyncIterator[Message]:
            yield req

        return await self._client.call_streaming(
            url,
            single_req(),
            response_type,
            extra_headers=extra_headers,
            timeout_seconds=timeout_seconds,
        )

    async def call_bidirectional_streaming(
        self,
        url: str,
        reqs: StreamInput[Message],
        response_type: type[T],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> AsyncStreamOutput[T]:
        async_iter = self._to_async_iterator(reqs)
        return await self._client.call_streaming(
            url,
            async_iter,
            response_type,
            extra_headers=extra_headers,
            timeout_seconds=timeout_seconds,
        )
