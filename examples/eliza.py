from collections.abc import AsyncIterator
from typing import Protocol

import aiohttp
import eliza_pb2  # type: ignore[import-not-found]

from connectrpc.client import ConnectClient
from connectrpc.client import ConnectProtocol
from connectrpc.streams import StreamInput
from connectrpc.streams import StreamOutput


class ElizaService(Protocol):
    async def say(self, req: eliza_pb2.SayRequest) -> eliza_pb2.SayResponse: ...

    def converse(self, reqs: StreamInput[eliza_pb2.ConverseRequest]) -> AsyncIterator[eliza_pb2.ConverseResponse]: ...

    def introduce(self, req: eliza_pb2.IntroduceRequest) -> AsyncIterator[eliza_pb2.IntroduceResponse]: ...

    async def converse_stream(
        self, reqs: StreamInput[eliza_pb2.ConverseRequest]
    ) -> StreamOutput[eliza_pb2.ConverseResponse]: ...

    async def introduce_stream(self, req: eliza_pb2.IntroduceRequest) -> StreamOutput[eliza_pb2.IntroduceResponse]: ...


class ElizaServiceClient(ElizaService):
    def __init__(
        self,
        base_url: str,
        http_client: aiohttp.ClientSession | None = None,
        protocol: ConnectProtocol = ConnectProtocol.CONNECT_PROTOBUF,
    ):
        self.base_url = base_url
        self._connect_client = ConnectClient(http_client, protocol)

    async def say(self, req: eliza_pb2.SayRequest) -> eliza_pb2.SayResponse:
        url = self.base_url + "/connectrpc.eliza.v1.ElizaService/Say"
        return await self._connect_client.call_unary(url, req, eliza_pb2.SayResponse)

    def converse(self, reqs: StreamInput[eliza_pb2.ConverseRequest]) -> AsyncIterator[eliza_pb2.ConverseResponse]:
        return self._converse_impl(reqs)

    async def _converse_impl(
        self, reqs: StreamInput[eliza_pb2.ConverseRequest]
    ) -> AsyncIterator[eliza_pb2.ConverseResponse]:
        async with await self.converse_stream(reqs) as stream:
            async for response in stream:
                yield response

    async def converse_stream(
        self, reqs: StreamInput[eliza_pb2.ConverseRequest]
    ) -> StreamOutput[eliza_pb2.ConverseResponse]:
        url = self.base_url + "/connectrpc.eliza.v1.ElizaService/Converse"
        return await self._connect_client.call_bidirectional_streaming(url, reqs, eliza_pb2.ConverseResponse)

    def introduce(self, req: eliza_pb2.IntroduceRequest) -> AsyncIterator[eliza_pb2.IntroduceResponse]:
        return self._introduce_impl(req)

    async def _introduce_impl(self, req: eliza_pb2.IntroduceRequest) -> AsyncIterator[eliza_pb2.IntroduceResponse]:
        async with await self.introduce_stream(req) as stream:
            async for response in stream:
                yield response

    async def introduce_stream(self, req: eliza_pb2.IntroduceRequest) -> StreamOutput[eliza_pb2.IntroduceResponse]:
        url = self.base_url + "/connectrpc.eliza.v1.ElizaService/Introduce"
        return await self._connect_client.call_server_streaming(url, req, eliza_pb2.IntroduceResponse)
