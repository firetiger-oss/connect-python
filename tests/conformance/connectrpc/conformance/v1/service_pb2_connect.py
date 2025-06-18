# Generated Connect client code

from collections.abc import AsyncIterator
import aiohttp

from connectrpc.client import ConnectClient
from connectrpc.client import ConnectProtocol
from connectrpc.headers import HeaderInput
from connectrpc.streams import StreamInput
from connectrpc.streams import StreamOutput
from connectrpc.unary import UnaryOutput

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

    async def call_unary(
        self, req: connectrpc.conformance.v1.service_pb2.UnaryRequest,extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> UnaryOutput[connectrpc.conformance.v1.service_pb2.UnaryResponse]:
        """Low-level method to call Unary, granting access to errors and metadata"""
        url = self.base_url + "/connectrpc.conformance.v1.ConformanceService/Unary"
        return await self._connect_client.call_unary(url, req, connectrpc.conformance.v1.service_pb2.UnaryResponse,extra_headers, timeout_seconds)

    async def unary(
        self, req: connectrpc.conformance.v1.service_pb2.UnaryRequest,extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> connectrpc.conformance.v1.service_pb2.UnaryResponse:
        response = await self.call_unary(req, extra_headers, timeout_seconds)
        if response.error() is not None:
            raise response.error()
        return response.message()

    def server_stream(
        self, req: connectrpc.conformance.v1.service_pb2.ServerStreamRequest,extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> AsyncIterator[connectrpc.conformance.v1.service_pb2.ServerStreamResponse]:
        return self._server_stream_iterator(req, extra_headers, timeout_seconds)

    async def _server_stream_iterator(
        self, req: connectrpc.conformance.v1.service_pb2.ServerStreamRequest,extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> AsyncIterator[connectrpc.conformance.v1.service_pb2.ServerStreamResponse]:
        stream_output = await self.call_server_stream(req, extra_headers)
        if stream_output.error() is not None:
            raise stream_output.error()
        async with await stream_output as stream:
            async for response in stream:
                yield response

    async def call_server_stream(
        self, req: connectrpc.conformance.v1.service_pb2.ServerStreamRequest,extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> StreamOutput[connectrpc.conformance.v1.service_pb2.ServerStreamResponse]:
        """Low-level method to call ServerStream, granting access to errors and metadata"""
        url = self.base_url + "/connectrpc.conformance.v1.ConformanceService/ServerStream"
        return await self._connect_client.call_server_streaming(
            url, req, connectrpc.conformance.v1.service_pb2.ServerStreamResponse, extra_headers, timeout_seconds
        )

    async def call_client_stream(
        self, reqs: StreamInput[connectrpc.conformance.v1.service_pb2.ClientStreamRequest], extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> StreamOutput[connectrpc.conformance.v1.service_pb2.ClientStreamResponse]:
        """Low-level method to call ClientStream, granting access to errors and metadata"""
        url = self.base_url + "/connectrpc.conformance.v1.ConformanceService/ClientStream"
        return await self._connect_client.call_client_streaming(
            url, reqs, connectrpc.conformance.v1.service_pb2.ClientStreamResponse, extra_headers, timeout_seconds
        )

    async def client_stream(
        self, reqs: StreamInput[connectrpc.conformance.v1.service_pb2.ClientStreamRequest], extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> connectrpc.conformance.v1.service_pb2.ClientStreamResponse:
        stream_output = await self.call_client_stream(req, extra_headers)
        if stream_output.error() is not None:
            raise stream_output.error()
        async with await stream_output as stream:
            async for response in stream:
                return response

    def bidi_stream(
        self, reqs: StreamInput[connectrpc.conformance.v1.service_pb2.BidiStreamRequest], extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> AsyncIterator[connectrpc.conformance.v1.service_pb2.BidiStreamResponse]:
        return self._bidi_stream_iterator(reqs, extra_headers, timeout_seconds)

    async def _bidi_stream_iterator(
        self, reqs: StreamInput[connectrpc.conformance.v1.service_pb2.BidiStreamRequest], extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> AsyncIterator[connectrpc.conformance.v1.service_pb2.BidiStreamResponse]:
        stream_output = await self.call_bidi_stream(reqs, extra_headers, timeout_seconds)
        if stream_output.error() is not None:
            raise stream_output.error()
        async with await stream_output as stream:
            async for response in stream:
                yield response

    async def call_bidi_stream(
        self, reqs: StreamInput[connectrpc.conformance.v1.service_pb2.BidiStreamRequest], extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> StreamOutput[connectrpc.conformance.v1.service_pb2.BidiStreamResponse]:
        """Low-level method to call BidiStream, granting access to errors and metadata"""
        url = self.base_url + "/connectrpc.conformance.v1.ConformanceService/BidiStream"
        return await self._connect_client.call_bidirectional_streaming(
            url, reqs, connectrpc.conformance.v1.service_pb2.BidiStreamResponse, extra_headers, timeout_seconds
        )

    async def call_unimplemented(
        self, req: connectrpc.conformance.v1.service_pb2.UnimplementedRequest,extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> UnaryOutput[connectrpc.conformance.v1.service_pb2.UnimplementedResponse]:
        """Low-level method to call Unimplemented, granting access to errors and metadata"""
        url = self.base_url + "/connectrpc.conformance.v1.ConformanceService/Unimplemented"
        return await self._connect_client.call_unary(url, req, connectrpc.conformance.v1.service_pb2.UnimplementedResponse,extra_headers, timeout_seconds)

    async def unimplemented(
        self, req: connectrpc.conformance.v1.service_pb2.UnimplementedRequest,extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> connectrpc.conformance.v1.service_pb2.UnimplementedResponse:
        response = await self.call_unimplemented(req, extra_headers, timeout_seconds)
        if response.error() is not None:
            raise response.error()
        return response.message()

    async def call_idempotent_unary(
        self, req: connectrpc.conformance.v1.service_pb2.IdempotentUnaryRequest,extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> UnaryOutput[connectrpc.conformance.v1.service_pb2.IdempotentUnaryResponse]:
        """Low-level method to call IdempotentUnary, granting access to errors and metadata"""
        url = self.base_url + "/connectrpc.conformance.v1.ConformanceService/IdempotentUnary"
        return await self._connect_client.call_unary(url, req, connectrpc.conformance.v1.service_pb2.IdempotentUnaryResponse,extra_headers, timeout_seconds)

    async def idempotent_unary(
        self, req: connectrpc.conformance.v1.service_pb2.IdempotentUnaryRequest,extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> connectrpc.conformance.v1.service_pb2.IdempotentUnaryResponse:
        response = await self.call_idempotent_unary(req, extra_headers, timeout_seconds)
        if response.error() is not None:
            raise response.error()
        return response.message()

