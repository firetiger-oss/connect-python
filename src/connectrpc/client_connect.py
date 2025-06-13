from __future__ import annotations

import struct
from collections.abc import AsyncIterator
from typing import Any
from typing import TypeVar

import aiohttp
from google.protobuf.message import Message

from .client_base import BaseClient
from .connect_serialization import CONNECT_PROTOBUF_SERIALIZATION
from .connect_serialization import ConnectSerialization
from .errors import ConnectProtocolError
from .streams import StreamOutput
from .streams_connect import EndStreamResponse

T = TypeVar("T", bound=Message)


class ConnectProtocolClient(BaseClient):
    def __init__(
        self,
        http_client: aiohttp.ClientSession,
        serialization: ConnectSerialization = CONNECT_PROTOBUF_SERIALIZATION,
    ):
        self._http_client = http_client
        self.serde = serialization

    async def call_unary(self, url: str, req: Message, response_type: type[T]) -> T:
        data = self.serde.serialize(req)
        headers = {
            "Content-Type": self.serde.unary_content_type,
            "Connect-Protocol-Version": "1",
        }
        async with self._http_client.request("POST", url, data=data, headers=headers) as resp:
            if resp.status != 200:
                raise await self.unary_error(resp)

            if resp.headers["Content-Type"] != self.serde.unary_content_type:
                raise ConnectProtocolError(
                    f"got unexpected Content-Type in response: {resp.headers['Content-Type']}"
                )
            body = await resp.read()
            response_msg = self.serde.deserialize(body, response_type)

            return response_msg

    async def call_streaming(
        self, url: str, reqs: AsyncIterator[Message], response_type: type[T]
    ) -> StreamOutput[T]:
        headers = {
            "Content-Type": self.serde.streaming_content_type,
            "Connect-Protocol-Version": "1",
        }

        async def encoded_stream() -> AsyncIterator[bytes]:
            async for msg in reqs:
                encoded = self.serde.serialize(msg)
                envelope = struct.pack(">BI", 0, len(encoded))
                yield envelope + encoded

        payload = aiohttp.AsyncIterablePayload(encoded_stream())

        resp = await self._http_client.request("POST", url, data=payload, headers=headers)
        if resp.status != 200:
            # TODO: this needs more detail
            await resp.release()
            raise ConnectProtocolError("got non-200 response code to stream")

        if resp.headers["Content-Type"] != self.serde.streaming_content_type:
            await resp.release()
            raise ConnectProtocolError(
                f"got unexpected Content-Type in response: {resp.headers['Content-Type']}"
            )
        return ConnectStreamOutput(resp, response_type, self.serde)

    async def unary_error(self, resp: aiohttp.ClientResponse) -> Exception:
        txt = await resp.text()
        # todo: proper exception types
        return Exception(f"non 200 received, body: {resp}, txt: {txt}")


class ConnectStreamOutput(StreamOutput[T]):
    """Represents an iterator over the messages in a Connect protobuf-encoded
    streaming response.

    """

    def __init__(
        self, response: aiohttp.ClientResponse, response_type: type[T], serde: ConnectSerialization
    ):
        self._response = response
        self._response_body = response.content
        self._response_type = response_type
        self._serde = serde
        self._trailing_metadata: dict[str, Any] | None = None
        self._consumed = False
        self._released = False

    async def __anext__(self) -> T:
        if self._consumed:
            raise StopAsyncIteration

        try:
            envelope = await self._response_body.readexactly(5)
            if envelope[0] & 1:
                # message is compressed, which we dont currently handle
                raise NotImplementedError("cant handle compressed messages yet")
            if envelope[0] & 2:
                # This is an EndStreamResponse
                encoded = await self._response_body.read(-1)
                end_stream_response = EndStreamResponse.from_bytes(encoded)
                if end_stream_response.error is not None:
                    raise ValueError(end_stream_response.error)

                self._trailing_metadata = end_stream_response.metadata
                self._consumed = True

                # Stream is now complete - release connection before StopAsyncIteration
                await self.done()
                raise StopAsyncIteration

            length = struct.unpack(">I", envelope[1:5])[0]
            encoded = await self._response_body.readexactly(length)
            return self._serde.deserialize(encoded, self._response_type)
        except Exception:
            # Ensure connection is released on any exception
            await self.done()
            raise

    def __aiter__(self) -> AsyncIterator[T]:
        return self

    def trailing_metadata(self) -> dict[str, Any] | None:
        if not self._consumed:
            raise RuntimeError("Stream must be fully consumed before accessing trailing metadata")
        return self._trailing_metadata

    async def __aenter__(self) -> ConnectStreamOutput[T]:
        """Enter async context manager for automatic resource management."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit async context manager and clean up connection resources."""
        await self.done()

    async def done(self) -> None:
        """Explicitly release connection resources.

        Safe to call multiple times. Releases the HTTP connection back to
        the connection pool for reuse.
        """
        if not self._released:
            self._released = True
            await self._response.release()
