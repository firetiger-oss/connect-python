import aiohttp
from google.protobuf.message import Message

from .client_base import BaseClient
from .streams import ClientStream
from .streams import ServerStream


class ConnectJSONClient(BaseClient):
    def __init__(self, http_client: aiohttp.ClientSession):
        raise NotImplementedError

    async def call_unary(self, url: str, req: Message) -> Message:
        raise NotImplementedError

    async def call_client_streaming(self, url: str, reqs: ClientStream) -> Message:
        raise NotImplementedError

    async def call_server_streaming(self, url: str, req: Message) -> ServerStream:
        raise NotImplementedError

    async def call_bidirectional_streaming(
        self, url: str, reqs: ClientStream
    ) -> ServerStream:
        raise NotImplementedError
