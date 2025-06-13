from typing import Protocol, Awaitable, Optional, AsyncIterator

from connectrpc.streams import StreamInput, StreamOutput
from connectrpc.client import ConnectClient, ConnectProtocol
import aiohttp


import eliza_pb2


class ElizaService(Protocol):
    async def say(self, req: eliza_pb2.SayRequest) -> eliza_pb2.SayResponse:
        ...

    async def converse(self, reqs: StreamInput[eliza_pb2.ConverseRequest]) -> StreamOutput[eliza_pb2.ConverseResponse]:
        ...

    async def introduce(self, req: eliza_pb2.IntroduceRequest) -> StreamOutput[eliza_pb2.IntroduceResponse]:
        ...


class ElizaServiceClient(ElizaService):
    def __init__(self, base_url: str, http_client: Optional[aiohttp.ClientSession]=None, protocol: ConnectProtocol=ConnectProtocol.CONNECT_PROTOBUF):
        self.base_url = base_url
        self._connect_client = ConnectClient(http_client, protocol)

    async def say(self, req: eliza_pb2.SayRequest) -> eliza_pb2.SayResponse:
        url = self.base_url + "/connectrpc.eliza.v1.ElizaService/Say"
        return await self._connect_client.call_unary(url, req, eliza_pb2.SayResponse)

    async def converse(self, reqs: StreamInput[eliza_pb2.ConverseRequest]) -> StreamOutput[eliza_pb2.ConverseResponse]:
        url = self.base_url + "/connectrpc.eliza.v1.ElizaService/Converse"
        return await self._connect_client.call_bidirectional_streaming(url, reqs, eliza_pb2.ConverseResponse)

    async def introduce(self, req: eliza_pb2.IntroduceRequest) -> StreamOutput[eliza_pb2.IntroduceResponse]:
        url = self.base_url + "/connectrpc.eliza.v1.ElizaService/Introduce"
        return await self._connect_client.call_server_streaming(url, req, eliza_pb2.IntroduceResponse)
    
        

