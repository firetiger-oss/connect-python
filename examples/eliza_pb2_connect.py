# Generated Connect client code

from collections.abc import AsyncIterator
from collections.abc import Iterable
from collections.abc import Iterator

import aiohttp
import eliza_pb2
import urllib3

from connectrpc.client_async import AsyncConnectClient
from connectrpc.client_connect import ConnectProtocolError
from connectrpc.client_protocol import ConnectProtocol
from connectrpc.client_sync import ConnectClient
from connectrpc.headers import HeaderInput
from connectrpc.streams import StreamInput
from connectrpc.streams import StreamOutput
from connectrpc.streams import SynchronousStreamOutput
from connectrpc.unary import UnaryOutput


class ElizaServiceClient:
    def __init__(
        self,
        base_url: str,
        http_client: urllib3.PoolManager | None = None,
        protocol: ConnectProtocol = ConnectProtocol.CONNECT_PROTOBUF,
    ):
        self.base_url = base_url
        self._connect_client = ConnectClient(http_client, protocol)

    def call_say(
        self,
        req: eliza_pb2.SayRequest,
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> UnaryOutput[eliza_pb2.SayResponse]:
        """Low-level method to call Say, granting access to errors and metadata"""
        url = self.base_url + "/connectrpc.eliza.v1.ElizaService/Say"
        return self._connect_client.call_unary(
            url, req, eliza_pb2.SayResponse, extra_headers, timeout_seconds
        )

    def say(
        self,
        req: eliza_pb2.SayRequest,
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> eliza_pb2.SayResponse:
        response = self.call_say(req, extra_headers, timeout_seconds)
        err = response.error()
        if err is not None:
            raise err
        msg = response.message()
        if msg is None:
            raise ConnectProtocolError("missing response message")
        return msg

    def converse(
        self,
        reqs: Iterable[eliza_pb2.ConverseRequest],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> Iterator[eliza_pb2.ConverseResponse]:
        return self._converse_iterator(reqs, extra_headers, timeout_seconds)

    def _converse_iterator(
        self,
        reqs: Iterable[eliza_pb2.ConverseRequest],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> Iterator[eliza_pb2.ConverseResponse]:
        stream_output = self.call_converse(reqs, extra_headers, timeout_seconds)
        err = stream_output.error()
        if err is not None:
            raise err
        yield from stream_output

    def call_converse(
        self,
        reqs: Iterable[eliza_pb2.ConverseRequest],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> SynchronousStreamOutput[eliza_pb2.ConverseResponse]:
        """Low-level method to call Converse, granting access to errors and metadata"""
        url = self.base_url + "/connectrpc.eliza.v1.ElizaService/Converse"
        return self._connect_client.call_bidirectional_streaming(
            url, reqs, eliza_pb2.ConverseResponse, extra_headers, timeout_seconds
        )

    def introduce(
        self,
        req: eliza_pb2.IntroduceRequest,
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> Iterator[eliza_pb2.IntroduceResponse]:
        return self._introduce_iterator(req, extra_headers, timeout_seconds)

    def _introduce_iterator(
        self,
        req: eliza_pb2.IntroduceRequest,
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> Iterator[eliza_pb2.IntroduceResponse]:
        stream_output = self.call_introduce(req, extra_headers)
        err = stream_output.error()
        if err is not None:
            raise err
        yield from stream_output

    def call_introduce(
        self,
        req: eliza_pb2.IntroduceRequest,
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> SynchronousStreamOutput[eliza_pb2.IntroduceResponse]:
        """Low-level method to call Introduce, granting access to errors and metadata"""
        url = self.base_url + "/connectrpc.eliza.v1.ElizaService/Introduce"
        return self._connect_client.call_server_streaming(
            url, req, eliza_pb2.IntroduceResponse, extra_headers, timeout_seconds
        )


class AsyncElizaServiceClient:
    def __init__(
        self,
        base_url: str,
        http_client: aiohttp.ClientSession,
        protocol: ConnectProtocol = ConnectProtocol.CONNECT_PROTOBUF,
    ):
        self.base_url = base_url
        self._connect_client = AsyncConnectClient(http_client, protocol)

    async def call_say(
        self,
        req: eliza_pb2.SayRequest,
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> UnaryOutput[eliza_pb2.SayResponse]:
        """Low-level method to call Say, granting access to errors and metadata"""
        url = self.base_url + "/connectrpc.eliza.v1.ElizaService/Say"
        return await self._connect_client.call_unary(
            url, req, eliza_pb2.SayResponse, extra_headers, timeout_seconds
        )

    async def say(
        self,
        req: eliza_pb2.SayRequest,
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> eliza_pb2.SayResponse:
        response = await self.call_say(req, extra_headers, timeout_seconds)
        err = response.error()
        if err is not None:
            raise err
        msg = response.message()
        if msg is None:
            raise ConnectProtocolError("missing response message")
        return msg

    def converse(
        self,
        reqs: StreamInput[eliza_pb2.ConverseRequest],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> AsyncIterator[eliza_pb2.ConverseResponse]:
        return self._converse_iterator(reqs, extra_headers, timeout_seconds)

    async def _converse_iterator(
        self,
        reqs: StreamInput[eliza_pb2.ConverseRequest],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> AsyncIterator[eliza_pb2.ConverseResponse]:
        stream_output = await self.call_converse(reqs, extra_headers, timeout_seconds)
        err = stream_output.error()
        if err is not None:
            raise err
        async with stream_output as stream:
            async for response in stream:
                yield response

    async def call_converse(
        self,
        reqs: StreamInput[eliza_pb2.ConverseRequest],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> StreamOutput[eliza_pb2.ConverseResponse]:
        """Low-level method to call Converse, granting access to errors and metadata"""
        url = self.base_url + "/connectrpc.eliza.v1.ElizaService/Converse"
        return await self._connect_client.call_bidirectional_streaming(
            url, reqs, eliza_pb2.ConverseResponse, extra_headers, timeout_seconds
        )

    def introduce(
        self,
        req: eliza_pb2.IntroduceRequest,
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> AsyncIterator[eliza_pb2.IntroduceResponse]:
        return self._introduce_iterator(req, extra_headers, timeout_seconds)

    async def _introduce_iterator(
        self,
        req: eliza_pb2.IntroduceRequest,
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> AsyncIterator[eliza_pb2.IntroduceResponse]:
        stream_output = await self.call_introduce(req, extra_headers)
        err = stream_output.error()
        if err is not None:
            raise err
        async with stream_output as stream:
            async for response in stream:
                yield response

    async def call_introduce(
        self,
        req: eliza_pb2.IntroduceRequest,
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> StreamOutput[eliza_pb2.IntroduceResponse]:
        """Low-level method to call Introduce, granting access to errors and metadata"""
        url = self.base_url + "/connectrpc.eliza.v1.ElizaService/Introduce"
        return await self._connect_client.call_server_streaming(
            url, req, eliza_pb2.IntroduceResponse, extra_headers, timeout_seconds
        )
