# Generated Connect client code

from collections.abc import AsyncIterator
import aiohttp

from connectrpc.client import ConnectClient
from connectrpc.client import ConnectProtocol
from connectrpc.streams import StreamInput
from connectrpc.streams import StreamOutput

import connectrpc.conformance.v1.service_pb2

class ConformanceServiceClient:
    def __init__(
        self,
        base_url: str,
        http_client: aiohttp.ClientSession | None = None,
        protocol: ConnectProtocol = ConnectProtocol.CONNECT_PROTOBUF,
    ):
        self.base_url = base_url
        self._connect_client = ConnectClient(http_client, protocol)

    async def unary(self, req: connectrpc.conformance.v1.service_pb2.UnaryRequest, extra_headers: dict[str, str] | None=None) -> connectrpc.conformance.v1.service_pb2.UnaryResponse:
        url = self.base_url + "/connectrpc.conformance.v1.ConformanceService/Unary"
        return await self._connect_client.call_unary(url, req, connectrpc.conformance.v1.service_pb2.UnaryResponse, extra_headers)

    def server_stream(
        self, req: connectrpc.conformance.v1.service_pb2.ServerStreamRequest, extra_headers: dict[str, str] | None=None
    ) -> AsyncIterator[connectrpc.conformance.v1.service_pb2.ServerStreamResponse]:
        return self._server_stream_impl(req, extra_headers)

    async def _server_stream_impl(
        self, req: connectrpc.conformance.v1.service_pb2.ServerStreamRequest, extra_headers: dict[str, str] | None=None
    ) -> AsyncIterator[connectrpc.conformance.v1.service_pb2.ServerStreamResponse]:
        async with await self.server_stream_stream(req, extra_headers) as stream:
            async for response in stream:
                yield response

    async def server_stream_stream(
        self, req: connectrpc.conformance.v1.service_pb2.ServerStreamRequest, extra_headers: dict[str, str] | None=None
    ) -> StreamOutput[connectrpc.conformance.v1.service_pb2.ServerStreamResponse]:
        url = self.base_url + "/connectrpc.conformance.v1.ConformanceService/ServerStream"
        return await self._connect_client.call_server_streaming(
            url, req, connectrpc.conformance.v1.service_pb2.ServerStreamResponse, extra_headers
        )

    async def client_stream(
        self, reqs: StreamInput[connectrpc.conformance.v1.service_pb2.ClientStreamRequest], extra_headers: dict[str, str] | None=None
    ) -> connectrpc.conformance.v1.service_pb2.ClientStreamResponse:
        url = self.base_url + "/connectrpc.conformance.v1.ConformanceService/ClientStream"
        return await self._connect_client.call_client_streaming(
            url, reqs, connectrpc.conformance.v1.service_pb2.ClientStreamResponse, extra_headers
        )

    def bidi_stream(
        self, reqs: StreamInput[connectrpc.conformance.v1.service_pb2.BidiStreamRequest], extra_headers: dict[str, str] | None=None
    ) -> AsyncIterator[connectrpc.conformance.v1.service_pb2.BidiStreamResponse]:
        return self._bidi_stream_impl(reqs, extra_headers)

    async def _bidi_stream_impl(
        self, reqs: StreamInput[connectrpc.conformance.v1.service_pb2.BidiStreamRequest], extra_headers: dict[str, str] | None=None
    ) -> AsyncIterator[connectrpc.conformance.v1.service_pb2.BidiStreamResponse]:
        async with await self.bidi_stream_stream(reqs, extra_headers) as stream:
            async for response in stream:
                yield response

    async def bidi_stream_stream(
        self, reqs: StreamInput[connectrpc.conformance.v1.service_pb2.BidiStreamRequest], extra_headers: dict[str, str] | None=None
    ) -> StreamOutput[connectrpc.conformance.v1.service_pb2.BidiStreamResponse]:
        url = self.base_url + "/connectrpc.conformance.v1.ConformanceService/BidiStream"
        return await self._connect_client.call_bidirectional_streaming(
            url, reqs, connectrpc.conformance.v1.service_pb2.BidiStreamResponse, extra_headers
        )

    async def unimplemented(self, req: connectrpc.conformance.v1.service_pb2.UnimplementedRequest, extra_headers: dict[str, str] | None=None) -> connectrpc.conformance.v1.service_pb2.UnimplementedResponse:
        url = self.base_url + "/connectrpc.conformance.v1.ConformanceService/Unimplemented"
        return await self._connect_client.call_unary(url, req, connectrpc.conformance.v1.service_pb2.UnimplementedResponse, extra_headers)

    async def idempotent_unary(self, req: connectrpc.conformance.v1.service_pb2.IdempotentUnaryRequest, extra_headers: dict[str, str] | None=None) -> connectrpc.conformance.v1.service_pb2.IdempotentUnaryResponse:
        url = self.base_url + "/connectrpc.conformance.v1.ConformanceService/IdempotentUnary"
        return await self._connect_client.call_unary(url, req, connectrpc.conformance.v1.service_pb2.IdempotentUnaryResponse, extra_headers)

