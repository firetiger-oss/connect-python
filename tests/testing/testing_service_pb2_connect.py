# Generated Connect client code

from __future__ import annotations

import sys
import typing
from collections.abc import AsyncIterator
from collections.abc import Iterable
from collections.abc import Iterator

import aiohttp
import urllib3

from connectrpc.client_async import AsyncConnectClient
from connectrpc.client_connect import ConnectProtocolError
from connectrpc.client_protocol import ConnectProtocol
from connectrpc.client_sync import ConnectClient
from connectrpc.headers import HeaderInput
from connectrpc.server import ClientRequest
from connectrpc.server import ClientStream
from connectrpc.server import ServerResponse
from connectrpc.server import ServerStream
from connectrpc.server_sync import ConnectWSGI
from connectrpc.streams import AsyncStreamOutput
from connectrpc.streams import StreamInput
from connectrpc.streams import StreamOutput
from connectrpc.unary import ClientStreamingOutput
from connectrpc.unary import UnaryOutput

if typing.TYPE_CHECKING:
    # wsgiref.types was added in Python 3.11.
    if sys.version_info >= (3, 11):
        from wsgiref.types import WSGIApplication
    else:
        from _typeshed.wsgi import WSGIApplication

import testing_service_pb2


class TestingServiceClient:
    def __init__(
        self,
        base_url: str,
        http_client: urllib3.PoolManager | None = None,
        protocol: ConnectProtocol = ConnectProtocol.CONNECT_PROTOBUF,
    ):
        self.base_url = base_url
        self._connect_client = ConnectClient(http_client, protocol)

    def call_echo(
        self,
        req: testing_service_pb2.EchoRequest,
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> UnaryOutput[testing_service_pb2.EchoResponse]:
        """Low-level method to call Echo, granting access to errors and metadata"""
        url = self.base_url + "/testing.TestingService/Echo"
        return self._connect_client.call_unary(
            url, req, testing_service_pb2.EchoResponse, extra_headers, timeout_seconds
        )

    def echo(
        self,
        req: testing_service_pb2.EchoRequest,
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> testing_service_pb2.EchoResponse:
        response = self.call_echo(req, extra_headers, timeout_seconds)
        err = response.error()
        if err is not None:
            raise err
        msg = response.message()
        if msg is None:
            raise ConnectProtocolError("missing response message")
        return msg

    def call_error(
        self,
        req: testing_service_pb2.ErrorRequest,
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> UnaryOutput[testing_service_pb2.ErrorResponse]:
        """Low-level method to call Error, granting access to errors and metadata"""
        url = self.base_url + "/testing.TestingService/Error"
        return self._connect_client.call_unary(
            url, req, testing_service_pb2.ErrorResponse, extra_headers, timeout_seconds
        )

    def error(
        self,
        req: testing_service_pb2.ErrorRequest,
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> testing_service_pb2.ErrorResponse:
        response = self.call_error(req, extra_headers, timeout_seconds)
        err = response.error()
        if err is not None:
            raise err
        msg = response.message()
        if msg is None:
            raise ConnectProtocolError("missing response message")
        return msg

    def call_header_test(
        self,
        req: testing_service_pb2.HeaderRequest,
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> UnaryOutput[testing_service_pb2.HeaderResponse]:
        """Low-level method to call HeaderTest, granting access to errors and metadata"""
        url = self.base_url + "/testing.TestingService/HeaderTest"
        return self._connect_client.call_unary(
            url, req, testing_service_pb2.HeaderResponse, extra_headers, timeout_seconds
        )

    def header_test(
        self,
        req: testing_service_pb2.HeaderRequest,
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> testing_service_pb2.HeaderResponse:
        response = self.call_header_test(req, extra_headers, timeout_seconds)
        err = response.error()
        if err is not None:
            raise err
        msg = response.message()
        if msg is None:
            raise ConnectProtocolError("missing response message")
        return msg

    def download(
        self,
        req: testing_service_pb2.DownloadRequest,
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> Iterator[testing_service_pb2.DownloadResponse]:
        return self._download_iterator(req, extra_headers, timeout_seconds)

    def _download_iterator(
        self,
        req: testing_service_pb2.DownloadRequest,
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> Iterator[testing_service_pb2.DownloadResponse]:
        stream_output = self.call_download(req, extra_headers)
        err = stream_output.error()
        if err is not None:
            raise err
        yield from stream_output
        err = stream_output.error()
        if err is not None:
            raise err

    def call_download(
        self,
        req: testing_service_pb2.DownloadRequest,
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> StreamOutput[testing_service_pb2.DownloadResponse]:
        """Low-level method to call Download, granting access to errors and metadata"""
        url = self.base_url + "/testing.TestingService/Download"
        return self._connect_client.call_server_streaming(
            url, req, testing_service_pb2.DownloadResponse, extra_headers, timeout_seconds
        )

    def call_upload(
        self,
        reqs: Iterable[testing_service_pb2.UploadRequest],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> ClientStreamingOutput[testing_service_pb2.UploadResponse]:
        """Low-level method to call Upload, granting access to errors and metadata"""
        url = self.base_url + "/testing.TestingService/Upload"
        return self._connect_client.call_client_streaming(
            url, reqs, testing_service_pb2.UploadResponse, extra_headers, timeout_seconds
        )

    def upload(
        self,
        reqs: Iterable[testing_service_pb2.UploadRequest],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> testing_service_pb2.UploadResponse:
        client_stream_output = self.call_upload(reqs, extra_headers)
        err = client_stream_output.error()
        if err is not None:
            raise err
        msg = client_stream_output.message()
        if msg is None:
            raise RuntimeError("ClientStreamOutput has empty error and message")
        return msg

    def chatter(
        self,
        reqs: Iterable[testing_service_pb2.ChatterRequest],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> Iterator[testing_service_pb2.ChatterResponse]:
        return self._chatter_iterator(reqs, extra_headers, timeout_seconds)

    def _chatter_iterator(
        self,
        reqs: Iterable[testing_service_pb2.ChatterRequest],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> Iterator[testing_service_pb2.ChatterResponse]:
        stream_output = self.call_chatter(reqs, extra_headers, timeout_seconds)
        err = stream_output.error()
        if err is not None:
            raise err
        yield from stream_output
        err = stream_output.error()
        if err is not None:
            raise err

    def call_chatter(
        self,
        reqs: Iterable[testing_service_pb2.ChatterRequest],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> StreamOutput[testing_service_pb2.ChatterResponse]:
        """Low-level method to call Chatter, granting access to errors and metadata"""
        url = self.base_url + "/testing.TestingService/Chatter"
        return self._connect_client.call_bidirectional_streaming(
            url, reqs, testing_service_pb2.ChatterResponse, extra_headers, timeout_seconds
        )


class AsyncTestingServiceClient:
    def __init__(
        self,
        base_url: str,
        http_client: aiohttp.ClientSession,
        protocol: ConnectProtocol = ConnectProtocol.CONNECT_PROTOBUF,
    ):
        self.base_url = base_url
        self._connect_client = AsyncConnectClient(http_client, protocol)

    async def call_echo(
        self,
        req: testing_service_pb2.EchoRequest,
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> UnaryOutput[testing_service_pb2.EchoResponse]:
        """Low-level method to call Echo, granting access to errors and metadata"""
        url = self.base_url + "/testing.TestingService/Echo"
        return await self._connect_client.call_unary(
            url, req, testing_service_pb2.EchoResponse, extra_headers, timeout_seconds
        )

    async def echo(
        self,
        req: testing_service_pb2.EchoRequest,
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> testing_service_pb2.EchoResponse:
        response = await self.call_echo(req, extra_headers, timeout_seconds)
        err = response.error()
        if err is not None:
            raise err
        msg = response.message()
        if msg is None:
            raise ConnectProtocolError("missing response message")
        return msg

    async def call_error(
        self,
        req: testing_service_pb2.ErrorRequest,
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> UnaryOutput[testing_service_pb2.ErrorResponse]:
        """Low-level method to call Error, granting access to errors and metadata"""
        url = self.base_url + "/testing.TestingService/Error"
        return await self._connect_client.call_unary(
            url, req, testing_service_pb2.ErrorResponse, extra_headers, timeout_seconds
        )

    async def error(
        self,
        req: testing_service_pb2.ErrorRequest,
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> testing_service_pb2.ErrorResponse:
        response = await self.call_error(req, extra_headers, timeout_seconds)
        err = response.error()
        if err is not None:
            raise err
        msg = response.message()
        if msg is None:
            raise ConnectProtocolError("missing response message")
        return msg

    async def call_header_test(
        self,
        req: testing_service_pb2.HeaderRequest,
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> UnaryOutput[testing_service_pb2.HeaderResponse]:
        """Low-level method to call HeaderTest, granting access to errors and metadata"""
        url = self.base_url + "/testing.TestingService/HeaderTest"
        return await self._connect_client.call_unary(
            url, req, testing_service_pb2.HeaderResponse, extra_headers, timeout_seconds
        )

    async def header_test(
        self,
        req: testing_service_pb2.HeaderRequest,
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> testing_service_pb2.HeaderResponse:
        response = await self.call_header_test(req, extra_headers, timeout_seconds)
        err = response.error()
        if err is not None:
            raise err
        msg = response.message()
        if msg is None:
            raise ConnectProtocolError("missing response message")
        return msg

    def download(
        self,
        req: testing_service_pb2.DownloadRequest,
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> AsyncIterator[testing_service_pb2.DownloadResponse]:
        return self._download_iterator(req, extra_headers, timeout_seconds)

    async def _download_iterator(
        self,
        req: testing_service_pb2.DownloadRequest,
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> AsyncIterator[testing_service_pb2.DownloadResponse]:
        stream_output = await self.call_download(req, extra_headers)
        err = stream_output.error()
        if err is not None:
            raise err
        async with stream_output as stream:
            async for response in stream:
                yield response
            err = stream.error()
            if err is not None:
                raise err

    async def call_download(
        self,
        req: testing_service_pb2.DownloadRequest,
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> AsyncStreamOutput[testing_service_pb2.DownloadResponse]:
        """Low-level method to call Download, granting access to errors and metadata"""
        url = self.base_url + "/testing.TestingService/Download"
        return await self._connect_client.call_server_streaming(
            url, req, testing_service_pb2.DownloadResponse, extra_headers, timeout_seconds
        )

    async def call_upload(
        self,
        reqs: StreamInput[testing_service_pb2.UploadRequest],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> ClientStreamingOutput[testing_service_pb2.UploadResponse]:
        """Low-level method to call Upload, granting access to errors and metadata"""
        url = self.base_url + "/testing.TestingService/Upload"
        return await self._connect_client.call_client_streaming(
            url, reqs, testing_service_pb2.UploadResponse, extra_headers, timeout_seconds
        )

    async def upload(
        self,
        reqs: StreamInput[testing_service_pb2.UploadRequest],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> testing_service_pb2.UploadResponse:
        client_stream_output = await self.call_upload(reqs, extra_headers)
        err = client_stream_output.error()
        if err is not None:
            raise err
        msg = client_stream_output.message()
        if msg is None:
            raise RuntimeError("ClientStreamOutput has empty error and message")
        return msg

    def chatter(
        self,
        reqs: StreamInput[testing_service_pb2.ChatterRequest],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> AsyncIterator[testing_service_pb2.ChatterResponse]:
        return self._chatter_iterator(reqs, extra_headers, timeout_seconds)

    async def _chatter_iterator(
        self,
        reqs: StreamInput[testing_service_pb2.ChatterRequest],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> AsyncIterator[testing_service_pb2.ChatterResponse]:
        stream_output = await self.call_chatter(reqs, extra_headers, timeout_seconds)
        err = stream_output.error()
        if err is not None:
            raise err
        async with stream_output as stream:
            async for response in stream:
                yield response
            err = stream.error()
            if err is not None:
                raise err

    async def call_chatter(
        self,
        reqs: StreamInput[testing_service_pb2.ChatterRequest],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> AsyncStreamOutput[testing_service_pb2.ChatterResponse]:
        """Low-level method to call Chatter, granting access to errors and metadata"""
        url = self.base_url + "/testing.TestingService/Chatter"
        return await self._connect_client.call_bidirectional_streaming(
            url, reqs, testing_service_pb2.ChatterResponse, extra_headers, timeout_seconds
        )


@typing.runtime_checkable
class TestingServiceProtocol(typing.Protocol):
    def echo(
        self, req: ClientRequest[testing_service_pb2.EchoRequest]
    ) -> ServerResponse[testing_service_pb2.EchoResponse]: ...
    def error(
        self, req: ClientRequest[testing_service_pb2.ErrorRequest]
    ) -> ServerResponse[testing_service_pb2.ErrorResponse]: ...
    def header_test(
        self, req: ClientRequest[testing_service_pb2.HeaderRequest]
    ) -> ServerResponse[testing_service_pb2.HeaderResponse]: ...
    def download(
        self, req: ClientRequest[testing_service_pb2.DownloadRequest]
    ) -> ServerStream[testing_service_pb2.DownloadResponse]: ...
    def upload(
        self, req: ClientStream[testing_service_pb2.UploadRequest]
    ) -> ServerResponse[testing_service_pb2.UploadResponse]: ...
    def chatter(
        self, req: ClientStream[testing_service_pb2.ChatterRequest]
    ) -> ServerStream[testing_service_pb2.ChatterResponse]: ...


TESTING_SERVICE_PATH_PREFIX = "/testing.TestingService"


def wsgi_testing_service(implementation: TestingServiceProtocol) -> WSGIApplication:
    app = ConnectWSGI()
    app.register_unary_rpc(
        "/testing.TestingService/Echo", implementation.echo, testing_service_pb2.EchoRequest
    )
    app.register_unary_rpc(
        "/testing.TestingService/Error", implementation.error, testing_service_pb2.ErrorRequest
    )
    app.register_unary_rpc(
        "/testing.TestingService/HeaderTest",
        implementation.header_test,
        testing_service_pb2.HeaderRequest,
    )
    app.register_server_streaming_rpc(
        "/testing.TestingService/Download",
        implementation.download,
        testing_service_pb2.DownloadRequest,
    )
    app.register_client_streaming_rpc(
        "/testing.TestingService/Upload", implementation.upload, testing_service_pb2.UploadRequest
    )
    app.register_bidi_streaming_rpc(
        "/testing.TestingService/Chatter",
        implementation.chatter,
        testing_service_pb2.ChatterRequest,
    )
    return app
