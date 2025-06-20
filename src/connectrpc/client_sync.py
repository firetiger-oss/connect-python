from __future__ import annotations

from collections.abc import Iterable
from typing import TypeVar

import urllib3
from google.protobuf.message import Message

from .client_base import BaseClient
from .client_connect import ConnectProtocolClient
from .client_grpc import ConnectGRPCClient
from .client_grpc_web import ConnectGRPCWebClient
from .client_protocol import ConnectProtocol
from .connect_serialization import CONNECT_JSON_SERIALIZATION
from .connect_serialization import CONNECT_PROTOBUF_SERIALIZATION
from .headers import HeaderInput
from .streams import StreamOutput
from .unary import ClientStreamingOutput
from .unary import UnaryOutput

T = TypeVar("T", bound=Message)


class ConnectClient:
    _client: BaseClient
    protocol: ConnectProtocol

    def __init__(
        self,
        http_client: urllib3.PoolManager | None = None,
        protocol: ConnectProtocol = ConnectProtocol.CONNECT_PROTOBUF,
    ):
        self.protocol = protocol

        if http_client is None:
            http_client = urllib3.PoolManager()

        if protocol == ConnectProtocol.CONNECT_PROTOBUF:
            self._client = ConnectProtocolClient(http_client, CONNECT_PROTOBUF_SERIALIZATION)
        elif protocol == ConnectProtocol.CONNECT_JSON:
            self._client = ConnectProtocolClient(http_client, CONNECT_JSON_SERIALIZATION)
        elif protocol == ConnectProtocol.GRPC:
            self._client = ConnectGRPCClient(http_client)
        elif protocol == ConnectProtocol.GRPC_WEB:
            self._client = ConnectGRPCWebClient(http_client)

    def call_unary(
        self,
        url: str,
        req: Message,
        response_type: type[T],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> UnaryOutput[T]:
        return self._client.call_unary(
            url, req, response_type, extra_headers=extra_headers, timeout_seconds=timeout_seconds
        )

    def call_client_streaming(
        self,
        url: str,
        reqs: Iterable[Message],
        response_type: type[T],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> ClientStreamingOutput[T]:
        stream_output = self._client.call_streaming(
            url,
            reqs,
            response_type,
            extra_headers=extra_headers,
            timeout_seconds=timeout_seconds,
        )
        return ClientStreamingOutput.from_stream_output(stream_output)

    def call_server_streaming(
        self,
        url: str,
        req: Message,
        response_type: type[T],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> StreamOutput[T]:
        return self._client.call_streaming(
            url,
            [req],
            response_type,
            extra_headers=extra_headers,
            timeout_seconds=timeout_seconds,
        )

    def call_bidirectional_streaming(
        self,
        url: str,
        reqs: Iterable[Message],
        response_type: type[T],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> StreamOutput[T]:
        return self._client.call_streaming(
            url,
            reqs,
            response_type,
            extra_headers=extra_headers,
            timeout_seconds=timeout_seconds,
        )
