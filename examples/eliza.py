from typing import Protocol, Awaitable

from connectrpc.streams import Stream

import eliza_pb2


class SynchronousElizaService(Protocol):
    def say(self, req: eliza_pb2.SayRequest) -> eliza_pb2.SayResponse:
        ...

    def converse(self, reqs: Stream[eliza_pb2.ConverseRequest]) -> Stream[eliza_pb2.ConverseResponse]:
        ...

    def introduce(self, req: eliza_pb2.IntroduceRequest) -> Stream[eliza_pb2.IntroduceResponse]:
        ...


class AsynchronousElizaService(Protocol):
    async def say(self, req: eliza_pb2.SayRequest) -> Awaitable[eliza_pb2.SayResponse]:
        ...

    async def converse(self, reqs: Stream[eliza_pb2.ConverseRequest]) -> Stream[eliza_pb2.ConverseResponse]:
        ...

    async def introduce(self, req: eliza_pb2.IntroduceRequest) -> Stream[eliza_pb2.IntroduceResponse]:
        ...


class ElizaServiceClient(ElizaService):
    pass


class SynchronousElizaServiceClient(SynchronousElizaService):
    pass
