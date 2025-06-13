import aiohttp
import struct
import base64
from google.protobuf.message import Message
from typing import Type, TypeVar, AsyncIterator
from collections.abc import Iterable

from .errors import ConnectProtocolError
from .client_base import BaseClient
from .streams import StreamInput, EndStreamResponse

T = TypeVar("T", bound=Message)


class ConnectProtobufClient(BaseClient):
    def __init__(self, http_client: aiohttp.ClientSession):
        self._http_client = http_client

    async def call_unary(self, url: str, req: Message, response_type: Type[T]) -> T:
        data = req.SerializeToString()
        headers = {
            "Content-Type": "application/proto",
            "Connect-Protocol-Version": "1",
        }
        async with self._http_client.request(
            "POST", url, data=data, headers=headers
        ) as resp:
            if resp.status != 200:
                raise await self.unary_error(resp)

            if resp.headers["Content-Type"] != "application/proto":
                raise ConnectProtocolError(
                    f"got unexpected Content-Type in response: {resp.headers['Content-Type']}"
                )
            body = await resp.read()
            response_msg = response_type()
            response_msg.ParseFromString(body)

            return response_msg

    def call_streaming(
        self, url: str, reqs: StreamInput[Message], response_type: Type[T]
    ) -> AsyncIterator[T]:
        return self._call_streaming_impl(url, reqs, response_type)

    async def _call_streaming_impl(
        self, url: str, reqs: StreamInput[Message], response_type: Type[T]
    ) -> AsyncIterator[T]:
        headers = {
            "Content-Type": "application/connect+proto",
            "Connect-Protocol-Version": "1",
        }

        async def encoded_stream() -> AsyncIterator[bytes]:
            async for msg in reqs:
                encoded = msg.SerializeToString()
                envelope = struct.pack(">BI", 0, len(encoded))
                yield envelope + encoded

        payload = aiohttp.AsyncIterablePayload(encoded_stream())

        async with self._http_client.request(
            "POST", url, data=payload, headers=headers
        ) as resp:
            if resp.status != 200:
                # TODO: this needs more detail
                raise ConnectProtocolError(f"got non-200 response code to stream")

            if resp.headers["Content-Type"] != "application/connect+proto":
                raise ConnectProtocolError(
                    f"got unexpected Content-Type in response: {resp.headers['Content-Type']}"
                )
            while True:
                envelope = await resp.content.readexactly(5)
                if envelope[0] & 1:
                    # message is compressed, which we dont currently handle
                    raise NotImplementedError("cant handle compressed messages yet")
                if envelope[0] & 2:
                    # This is an EndStreamResponse
                    encoded = await resp.content.read(-1)
                    end_stream_response = EndStreamResponse.from_bytes(encoded)
                    if end_stream_response.error is not None:
                        raise ValueError(end_stream_response.error)
                    return

                length = struct.unpack(">I", envelope[1:5])[0]
                encoded = await resp.content.readexactly(length)
                msg = response_type()
                msg.ParseFromString(encoded)
                yield msg

    async def unary_error(self, resp: aiohttp.ClientResponse) -> Exception:
        txt = await resp.text()
        # todo: proper exception types
        return Exception(f"non 200 received, body: {resp}, txt: {txt}")
