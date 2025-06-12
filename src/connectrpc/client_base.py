from google.protobuf.message import Message
from typing import Protocol

from .streams import ClientStream
from .streams import ServerStream


class BaseClient(Protocol):
    async def call_unary(self, url: str, req: Message) -> Message: ...

    async def call_client_streaming(self, url: str, reqs: ClientStream) -> Message: ...

    async def call_server_streaming(self, url: str, req: Message) -> ServerStream: ...

    async def call_bidirectional_streaming(
        self, url: str, reqs: ClientStream
    ) -> ServerStream: ...
