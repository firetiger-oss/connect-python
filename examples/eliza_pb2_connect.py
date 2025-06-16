# Generated Connect client code

from collections.abc import AsyncIterator
import aiohttp

from connectrpc.client import ConnectClient
from connectrpc.client import ConnectProtocol
from connectrpc.streams import StreamInput
from connectrpc.streams import StreamOutput


class ElizaServiceClient:
    def __init__(
        self,
        base_url: str,
        http_client: aiohttp.ClientSession | None = None,
        protocol: ConnectProtocol = ConnectProtocol.CONNECT_PROTOBUF,
    ):
        self.base_url = base_url
        self._connect_client = ConnectClient(http_client, protocol)

    async def say(self, req: SayRequest) -> SayResponse:
        url = self.base_url + "/connectrpc.eliza.v1.ElizaService/Say"
        return await self._connect_client.call_unary(url, req, SayResponse)

    def converse(
        self, reqs: StreamInput[ConverseRequest]
    ) -> AsyncIterator[ConverseResponse]:
        return self._converse_impl(reqs)

    async def _converse_impl(
        self, reqs: StreamInput[ConverseRequest]
    ) -> AsyncIterator[ConverseResponse]:
        async with await self.converse_stream(reqs) as stream:
            async for response in stream:
                yield response

    async def converse_stream(
        self, reqs: StreamInput[ConverseRequest]
    ) -> StreamOutput[ConverseResponse]:
        url = self.base_url + "/connectrpc.eliza.v1.ElizaService/Converse"
        return await self._connect_client.call_bidirectional_streaming(
            url, reqs, ConverseResponse
        )

    def introduce(
        self, req: IntroduceRequest
    ) -> AsyncIterator[IntroduceResponse]:
        return self._introduce_impl(req)

    async def _introduce_impl(
        self, req: IntroduceRequest
    ) -> AsyncIterator[IntroduceResponse]:
        async with await self.introduce_stream(req) as stream:
            async for response in stream:
                yield response

    async def introduce_stream(
        self, req: IntroduceRequest
    ) -> StreamOutput[IntroduceResponse]:
        url = self.base_url + "/connectrpc.eliza.v1.ElizaService/Introduce"
        return await self._connect_client.call_server_streaming(
            url, req, IntroduceResponse
        )

