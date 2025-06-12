from __future__ import annotations

from enum import Enum

import aiohttp
from google.protobuf.message import Message

from .client_base import BaseClient
from .client_grpc import ConnectGRPCClient
from .client_grpc_web import ConnectGRPCWebClient
from .client_json import ConnectJSONClient
from .client_protobuf import ConnectProtobufClient
from .streams import ClientStream
from .streams import ServerStream


class ConnectProtocol(Enum):
    CONNECT_PROTOBUF = "connect-proto"
    CONNECT_JSON = "connect-json"
    GRPC = "grpc"
    GRPC_WEB = "grpc-web"


class ConnectClient:
    _client: BaseClient

    def __init__(
        self,
        http_client: aiohttp.ClientSession,
        protocol: ConnectProtocol = ConnectProtocol.CONNECT_PROTOBUF,
    ):
        if protocol == ConnectProtocol.CONNECT_PROTOBUF:
            self._client = ConnectProtobufClient(http_client)
        elif protocol == ConnectProtocol.CONNECT_JSON:
            self._client = ConnectJSONClient(http_client)            
        elif protocol == ConnectProtocol.GRPC:
            self._client = ConnectGRPCClient(http_client)                        
        elif protocol == ConnectProtocol.GRPC_WEB:
            self._client = ConnectGRPCWebClient(http_client)                                    

    async def call_unary(self, url: str, req: Message) -> Message:
        return await self._client.call_unary(url, req)

    async def call_client_streaming(self, url: str, reqs: ClientStream) -> Message:
        return await self._client.call_client_streaming(url, reqs)

    async def call_server_streaming(self, url: str, req: Message) -> ServerStream:
        return await self._client.call_server_streaming(url, req)

    async def call_bidirectional_streaming(
        self, url: str, reqs: ClientStream
    ) -> ServerStream:
        return await self._client.call_bidirectional_streaming(url, reqs)
