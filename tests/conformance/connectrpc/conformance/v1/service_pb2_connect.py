# Generated Connect client code

from collections.abc import AsyncIterator

import aiohttp

from connectrpc.client import ConnectClient
from connectrpc.client import ConnectProtocol
from connectrpc.conformance.v1.service_pb2 import BidiStreamRequest
from connectrpc.conformance.v1.service_pb2 import BidiStreamResponse
from connectrpc.conformance.v1.service_pb2 import ClientStreamRequest
from connectrpc.conformance.v1.service_pb2 import ClientStreamResponse
from connectrpc.conformance.v1.service_pb2 import IdempotentUnaryRequest
from connectrpc.conformance.v1.service_pb2 import IdempotentUnaryResponse
from connectrpc.conformance.v1.service_pb2 import ServerStreamRequest
from connectrpc.conformance.v1.service_pb2 import ServerStreamResponse
from connectrpc.conformance.v1.service_pb2 import UnaryRequest
from connectrpc.conformance.v1.service_pb2 import UnaryResponse
from connectrpc.conformance.v1.service_pb2 import UnimplementedRequest
from connectrpc.conformance.v1.service_pb2 import UnimplementedResponse
from connectrpc.streams import StreamInput
from connectrpc.streams import StreamOutput


class ConformanceServiceClient:
    def __init__(
        self,
        base_url: str,
        http_client: aiohttp.ClientSession | None = None,
        protocol: ConnectProtocol = ConnectProtocol.CONNECT_PROTOBUF,
    ):
        self.base_url = base_url
        self._connect_client = ConnectClient(http_client, protocol)

    async def unary(self, req: UnaryRequest) -> UnaryResponse:
        url = self.base_url + "/connectrpc.conformance.v1.ConformanceService/Unary"
        return await self._connect_client.call_unary(url, req, UnaryResponse)

    def serverstream(self, req: ServerStreamRequest) -> AsyncIterator[ServerStreamResponse]:
        return self._serverstream_impl(req)

    async def _serverstream_impl(
        self, req: ServerStreamRequest
    ) -> AsyncIterator[ServerStreamResponse]:
        async with await self.serverstream_stream(req) as stream:
            async for response in stream:
                yield response

    async def serverstream_stream(
        self, req: ServerStreamRequest
    ) -> StreamOutput[ServerStreamResponse]:
        url = self.base_url + "/connectrpc.conformance.v1.ConformanceService/ServerStream"
        return await self._connect_client.call_server_streaming(url, req, ServerStreamResponse)

    async def clientstream(self, reqs: StreamInput[ClientStreamRequest]) -> ClientStreamResponse:
        url = self.base_url + "/connectrpc.conformance.v1.ConformanceService/ClientStream"
        return await self._connect_client.call_client_streaming(url, reqs, ClientStreamResponse)

    def bidistream(self, reqs: StreamInput[BidiStreamRequest]) -> AsyncIterator[BidiStreamResponse]:
        return self._bidistream_impl(reqs)

    async def _bidistream_impl(
        self, reqs: StreamInput[BidiStreamRequest]
    ) -> AsyncIterator[BidiStreamResponse]:
        async with await self.bidistream_stream(reqs) as stream:
            async for response in stream:
                yield response

    async def bidistream_stream(
        self, reqs: StreamInput[BidiStreamRequest]
    ) -> StreamOutput[BidiStreamResponse]:
        url = self.base_url + "/connectrpc.conformance.v1.ConformanceService/BidiStream"
        return await self._connect_client.call_bidirectional_streaming(
            url, reqs, BidiStreamResponse
        )

    async def unimplemented(self, req: UnimplementedRequest) -> UnimplementedResponse:
        url = self.base_url + "/connectrpc.conformance.v1.ConformanceService/Unimplemented"
        return await self._connect_client.call_unary(url, req, UnimplementedResponse)

    async def idempotentunary(self, req: IdempotentUnaryRequest) -> IdempotentUnaryResponse:
        url = self.base_url + "/connectrpc.conformance.v1.ConformanceService/IdempotentUnary"
        return await self._connect_client.call_unary(url, req, IdempotentUnaryResponse)
