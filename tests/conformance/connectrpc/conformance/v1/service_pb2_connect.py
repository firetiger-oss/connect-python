# Generated Connect client code

from collections.abc import AsyncIterator
from collections.abc import Iterator
from collections.abc import Iterable
import aiohttp
import urllib3

from connectrpc.client_async import AsyncConnectClient
from connectrpc.client_sync import ConnectClient
from connectrpc.client_protocol import ConnectProtocol
from connectrpc.client_connect import ConnectProtocolError
from connectrpc.headers import HeaderInput
from connectrpc.streams import StreamInput
from connectrpc.streams import AsyncStreamOutput
from connectrpc.streams import StreamOutput
from connectrpc.unary import UnaryOutput
from connectrpc.unary import ClientStreamingOutput

import connectrpc.conformance.v1.service_pb2

class ConformanceServiceClient:
    def __init__(
        self,
        base_url: str,
        http_client: urllib3.PoolManager | None = None,
        protocol: ConnectProtocol = ConnectProtocol.CONNECT_PROTOBUF,
    ):
        self.base_url = base_url
        self._connect_client = ConnectClient(http_client, protocol)
    def call_unary(
        self, req: connectrpc.conformance.v1.service_pb2.UnaryRequest,extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> UnaryOutput[connectrpc.conformance.v1.service_pb2.UnaryResponse]:
        """Low-level method to call Unary, granting access to errors and metadata"""
        url = self.base_url + "/connectrpc.conformance.v1.ConformanceService/Unary"
        return self._connect_client.call_unary(url, req, connectrpc.conformance.v1.service_pb2.UnaryResponse,extra_headers, timeout_seconds)


    def unary(
        self, req: connectrpc.conformance.v1.service_pb2.UnaryRequest,extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> connectrpc.conformance.v1.service_pb2.UnaryResponse:
        response = self.call_unary(req, extra_headers, timeout_seconds)
        err = response.error()
        if err is not None:
            raise err
        msg = response.message()
        if msg is None:
            raise ConnectProtocolError('missing response message')
        return msg

    def server_stream(
        self, req: connectrpc.conformance.v1.service_pb2.ServerStreamRequest,extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> Iterator[connectrpc.conformance.v1.service_pb2.ServerStreamResponse]:
        return self._server_stream_iterator(req, extra_headers, timeout_seconds)

    def _server_stream_iterator(
        self, req: connectrpc.conformance.v1.service_pb2.ServerStreamRequest,extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> Iterator[connectrpc.conformance.v1.service_pb2.ServerStreamResponse]:
        stream_output = self.call_server_stream(req, extra_headers)
        err = stream_output.error()
        if err is not None:
            raise err
        yield from stream_output

    def call_server_stream(
        self, req: connectrpc.conformance.v1.service_pb2.ServerStreamRequest,extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> StreamOutput[connectrpc.conformance.v1.service_pb2.ServerStreamResponse]:
        """Low-level method to call ServerStream, granting access to errors and metadata"""
        url = self.base_url + "/connectrpc.conformance.v1.ConformanceService/ServerStream"
        return self._connect_client.call_server_streaming(
            url, req, connectrpc.conformance.v1.service_pb2.ServerStreamResponse, extra_headers, timeout_seconds
        )

    def call_client_stream(
        self, reqs: Iterable[connectrpc.conformance.v1.service_pb2.ClientStreamRequest], extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> ClientStreamingOutput[connectrpc.conformance.v1.service_pb2.ClientStreamResponse]:
        """Low-level method to call ClientStream, granting access to errors and metadata"""
        url = self.base_url + "/connectrpc.conformance.v1.ConformanceService/ClientStream"
        return self._connect_client.call_client_streaming(
            url, reqs, connectrpc.conformance.v1.service_pb2.ClientStreamResponse, extra_headers, timeout_seconds
        )

    def client_stream(
        self, reqs: Iterable[connectrpc.conformance.v1.service_pb2.ClientStreamRequest], extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> connectrpc.conformance.v1.service_pb2.ClientStreamResponse:
        client_stream_output = self.call_client_stream(reqs, extra_headers)
        err = client_stream_output.error()
        if err is not None:
            raise err
        msg = client_stream_output.message()
        if msg is None:
            raise RuntimeError('ClientStreamOutput has empty error and message')
        return msg

    def bidi_stream(
        self, reqs: Iterable[connectrpc.conformance.v1.service_pb2.BidiStreamRequest], extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> Iterator[connectrpc.conformance.v1.service_pb2.BidiStreamResponse]:
        return self._bidi_stream_iterator(reqs, extra_headers, timeout_seconds)

    def _bidi_stream_iterator(
        self, reqs: Iterable[connectrpc.conformance.v1.service_pb2.BidiStreamRequest], extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> Iterator[connectrpc.conformance.v1.service_pb2.BidiStreamResponse]:
        stream_output = self.call_bidi_stream(reqs, extra_headers, timeout_seconds)
        err = stream_output.error()
        if err is not None:
            raise err
        yield from stream_output

    def call_bidi_stream(
        self, reqs: Iterable[connectrpc.conformance.v1.service_pb2.BidiStreamRequest], extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> StreamOutput[connectrpc.conformance.v1.service_pb2.BidiStreamResponse]:
        """Low-level method to call BidiStream, granting access to errors and metadata"""
        url = self.base_url + "/connectrpc.conformance.v1.ConformanceService/BidiStream"
        return self._connect_client.call_bidirectional_streaming(
            url, reqs, connectrpc.conformance.v1.service_pb2.BidiStreamResponse, extra_headers, timeout_seconds
        )

    def call_unimplemented(
        self, req: connectrpc.conformance.v1.service_pb2.UnimplementedRequest,extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> UnaryOutput[connectrpc.conformance.v1.service_pb2.UnimplementedResponse]:
        """Low-level method to call Unimplemented, granting access to errors and metadata"""
        url = self.base_url + "/connectrpc.conformance.v1.ConformanceService/Unimplemented"
        return self._connect_client.call_unary(url, req, connectrpc.conformance.v1.service_pb2.UnimplementedResponse,extra_headers, timeout_seconds)


    def unimplemented(
        self, req: connectrpc.conformance.v1.service_pb2.UnimplementedRequest,extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> connectrpc.conformance.v1.service_pb2.UnimplementedResponse:
        response = self.call_unimplemented(req, extra_headers, timeout_seconds)
        err = response.error()
        if err is not None:
            raise err
        msg = response.message()
        if msg is None:
            raise ConnectProtocolError('missing response message')
        return msg

    def call_idempotent_unary(
        self, req: connectrpc.conformance.v1.service_pb2.IdempotentUnaryRequest,extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> UnaryOutput[connectrpc.conformance.v1.service_pb2.IdempotentUnaryResponse]:
        """Low-level method to call IdempotentUnary, granting access to errors and metadata"""
        url = self.base_url + "/connectrpc.conformance.v1.ConformanceService/IdempotentUnary"
        return self._connect_client.call_unary(url, req, connectrpc.conformance.v1.service_pb2.IdempotentUnaryResponse,extra_headers, timeout_seconds)


    def idempotent_unary(
        self, req: connectrpc.conformance.v1.service_pb2.IdempotentUnaryRequest,extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> connectrpc.conformance.v1.service_pb2.IdempotentUnaryResponse:
        response = self.call_idempotent_unary(req, extra_headers, timeout_seconds)
        err = response.error()
        if err is not None:
            raise err
        msg = response.message()
        if msg is None:
            raise ConnectProtocolError('missing response message')
        return msg

class AsyncConformanceServiceClient:
    def __init__(
        self,
        base_url: str,
        http_client: aiohttp.ClientSession,
        protocol: ConnectProtocol = ConnectProtocol.CONNECT_PROTOBUF,
    ):
        self.base_url = base_url
        self._connect_client = AsyncConnectClient(http_client, protocol)

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
        err = response.error()
        if err is not None:
            raise err
        msg = response.message()
        if msg is None:
            raise ConnectProtocolError('missing response message')
        return msg

    def server_stream(
        self, req: connectrpc.conformance.v1.service_pb2.ServerStreamRequest,extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> AsyncIterator[connectrpc.conformance.v1.service_pb2.ServerStreamResponse]:
        return self._server_stream_iterator(req, extra_headers, timeout_seconds)

    async def _server_stream_iterator(
        self, req: connectrpc.conformance.v1.service_pb2.ServerStreamRequest,extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> AsyncIterator[connectrpc.conformance.v1.service_pb2.ServerStreamResponse]:
        stream_output = await self.call_server_stream(req, extra_headers)
        err = stream_output.error()
        if err is not None:
            raise err
        async with stream_output as stream:
            async for response in stream:
                yield response

    async def call_server_stream(
        self, req: connectrpc.conformance.v1.service_pb2.ServerStreamRequest,extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> AsyncStreamOutput[connectrpc.conformance.v1.service_pb2.ServerStreamResponse]:
        """Low-level method to call ServerStream, granting access to errors and metadata"""
        url = self.base_url + "/connectrpc.conformance.v1.ConformanceService/ServerStream"
        return await self._connect_client.call_server_streaming(
            url, req, connectrpc.conformance.v1.service_pb2.ServerStreamResponse, extra_headers, timeout_seconds
        )

    async def call_client_stream(
        self, reqs: StreamInput[connectrpc.conformance.v1.service_pb2.ClientStreamRequest], extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> ClientStreamingOutput[connectrpc.conformance.v1.service_pb2.ClientStreamResponse]:
        """Low-level method to call ClientStream, granting access to errors and metadata"""
        url = self.base_url + "/connectrpc.conformance.v1.ConformanceService/ClientStream"
        return await self._connect_client.call_client_streaming(
            url, reqs, connectrpc.conformance.v1.service_pb2.ClientStreamResponse, extra_headers, timeout_seconds
        )

    async def client_stream(
        self, reqs: StreamInput[connectrpc.conformance.v1.service_pb2.ClientStreamRequest], extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> connectrpc.conformance.v1.service_pb2.ClientStreamResponse:
        client_stream_output = await self.call_client_stream(reqs, extra_headers)
        err = client_stream_output.error()
        if err is not None:
            raise err
        msg = client_stream_output.message()
        if msg is None:
            raise RuntimeError('ClientStreamOutput has empty error and message')
        return msg

    def bidi_stream(
        self, reqs: StreamInput[connectrpc.conformance.v1.service_pb2.BidiStreamRequest], extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> AsyncIterator[connectrpc.conformance.v1.service_pb2.BidiStreamResponse]:
        return self._bidi_stream_iterator(reqs, extra_headers, timeout_seconds)

    async def _bidi_stream_iterator(
        self, reqs: StreamInput[connectrpc.conformance.v1.service_pb2.BidiStreamRequest], extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> AsyncIterator[connectrpc.conformance.v1.service_pb2.BidiStreamResponse]:
        stream_output = await self.call_bidi_stream(reqs, extra_headers, timeout_seconds)
        err = stream_output.error()
        if err is not None:
            raise err
        async with stream_output as stream:
            async for response in stream:
                yield response

    async def call_bidi_stream(
        self, reqs: StreamInput[connectrpc.conformance.v1.service_pb2.BidiStreamRequest], extra_headers: HeaderInput | None=None, timeout_seconds: float | None=None
    ) -> AsyncStreamOutput[connectrpc.conformance.v1.service_pb2.BidiStreamResponse]:
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
        err = response.error()
        if err is not None:
            raise err
        msg = response.message()
        if msg is None:
            raise ConnectProtocolError('missing response message')
        return msg

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
        err = response.error()
        if err is not None:
            raise err
        msg = response.message()
        if msg is None:
            raise ConnectProtocolError('missing response message')
        return msg

