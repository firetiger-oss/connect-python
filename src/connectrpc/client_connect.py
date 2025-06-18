from __future__ import annotations

import struct
from collections.abc import AsyncIterator
from typing import Any
from typing import TypeVar

import aiohttp
from google.protobuf.message import Message
from multidict import CIMultiDict

from .client_base import BaseClient
from .connect_serialization import CONNECT_PROTOBUF_SERIALIZATION
from .connect_serialization import ConnectSerialization
from .debugprint import debug
from .errors import ConnectError
from .headers import HeaderInput
from .headers import merge_headers
from .streams import StreamOutput
from .streams_connect import EndStreamResponse
from .unary import UnaryOutput

T = TypeVar("T", bound=Message)


class ConnectProtocolClient(BaseClient):
    def __init__(
        self,
        http_client: aiohttp.ClientSession,
        serialization: ConnectSerialization = CONNECT_PROTOBUF_SERIALIZATION,
    ):
        self._http_client = http_client
        self.serde = serialization

    async def call_unary(
        self,
        url: str,
        req: Message,
        response_type: type[T],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> UnaryOutput[T]:
        data = self.serde.serialize(req)
        headers = CIMultiDict(
            [
                ("Content-Type", self.serde.unary_content_type),
                ("Connect-Protocol-Version", "1"),
            ]
        )
        headers = merge_headers(headers, extra_headers)
        debug("ConnectProtocolClient.call_unary timeout_seconds=", timeout_seconds)
        if timeout_seconds is not None and timeout_seconds > 0:
            headers["Connect-Timeout-Ms"] = str(int(timeout_seconds * 1000))
            timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        else:
            timeout = aiohttp.ClientTimeout(total=None)
        debug("ConnectProtocolClient.call_unary timeout=", timeout)
        async with self._http_client.request(
            "POST", url, data=data, headers=headers, timeout=timeout
        ) as resp:
            output: ConnectUnaryOutput[T] = ConnectUnaryOutput(
                response_headers=CIMultiDict(resp.headers)
            )
            if resp.status != 200:
                output._error = await self.unary_error(resp)
                return output

            if resp.headers["Content-Type"] != self.serde.unary_content_type:
                raise UnexpectedContentType(resp.headers["Content-Type"])

            try:
                body = await resp.read()
                response_msg = self.serde.deserialize(body, response_type)
            except Exception as e:
                from .errors import ConnectErrorCode

                output._error = ConnectError(ConnectErrorCode.INTERNAL, str(e))
                raise ConnectPartialUnaryResponse(output) from e

            output._message = response_msg
            return output

    async def call_streaming(
        self,
        url: str,
        reqs: AsyncIterator[Message],
        response_type: type[T],
        extra_headers: HeaderInput | None = None,
        timeout_seconds: float | None = None,
    ) -> StreamOutput[T]:
        headers = CIMultiDict(
            [
                ("Content-Type", self.serde.streaming_content_type),
                ("Connect-Protocol-Version", "1"),
            ]
        )
        headers = merge_headers(headers, extra_headers)

        async def encoded_stream() -> AsyncIterator[bytes]:
            async for msg in reqs:
                encoded = self.serde.serialize(msg)
                envelope = struct.pack(">BI", 0, len(encoded))
                yield envelope + encoded

        payload = aiohttp.AsyncIterablePayload(encoded_stream())

        if timeout_seconds is not None and timeout_seconds > 0:
            headers["Connect-Timeout-Ms"] = str(int(timeout_seconds * 1000))
            timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        else:
            timeout = aiohttp.ClientTimeout(total=None)

        http_response = await self._http_client.request(
            "POST", url, data=payload, headers=headers, timeout=timeout
        )
        if http_response.headers["Content-Type"] != self.serde.streaming_content_type:
            await http_response.release()
            raise UnexpectedContentType(http_response.headers["Content-Type"])

        stream_output = ConnectStreamOutput(http_response, response_type, self.serde)
        if http_response.status != 200:
            txt = await http_response.text()
            await stream_output._abort_with_error(
                ConnectError.from_http_response(http_response.status, txt)
            )
        return stream_output

    async def unary_error(self, resp: aiohttp.ClientResponse) -> ConnectError:
        txt = await resp.text()
        return ConnectError.from_http_response(resp.status, txt)


class ConnectUnaryOutput(UnaryOutput[T]):
    def __init__(self, response_headers: CIMultiDict[str], message: T | None = None):
        self._message = message
        self._response_headers = response_headers
        self._error: ConnectError | None = None

    def message(self) -> T | None:
        return self._message

    def response_headers(self) -> CIMultiDict[str]:
        trailers: CIMultiDict[str] = CIMultiDict()

        for key, value in self._response_headers.items():
            key_clean = str(key).lower()
            if key_clean.startswith("trailer-"):
                # Strip 'trailer-' prefix
                key_new = key_clean.removeprefix("trailer-")
                trailers.add(key_new, value)

        return self._response_headers

    def error(self) -> ConnectError | None:
        return self._error

    def response_trailers(self) -> CIMultiDict[str]:
        # Connect Unary responses encode trailers in headers
        trailers: CIMultiDict[str] = CIMultiDict()
        for key, value in self._response_headers.items():
            key_clean = str(key).lower()
            if key_clean.startswith("trailer-"):
                # Strip 'trailer-' prefix
                key_new = key_clean.removeprefix("trailer-")
                trailers.add(key_new, value)

        return trailers


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
        self._response_headers = CIMultiDict(response.headers)  # Capture HTTP response headers
        self._response_trailers: CIMultiDict[str] = CIMultiDict()
        self._consumed = False
        self._released = False
        self._error: ConnectError | None = None

    async def _abort_with_error(self, err: Exception) -> None:
        from .errors import ConnectErrorCode

        self._error = ConnectError(ConnectErrorCode.INTERNAL, str(err))
        await self.close()

    async def __anext__(self) -> T:
        if self._consumed or self._released:
            raise StopAsyncIteration
        envelope = await self._response_body.readexactly(5)
        if envelope[0] & 1:
            # message is compressed, which we dont currently handle
            raise NotImplementedError("cant handle compressed messages yet")
        if envelope[0] & 2:
            # This is an EndStreamResponse
            encoded = await self._response_body.read(-1)
            end_stream_response = EndStreamResponse.from_bytes(encoded)

            if end_stream_response.error is not None:
                self._error = end_stream_response.error

            self._response_trailers = end_stream_response.metadata
            self._consumed = True
            # Stream is now complete - release connection before StopAsyncIteration
            await self.close()

            raise StopAsyncIteration

        length = struct.unpack(">I", envelope[1:5])[0]
        encoded = await self._response_body.readexactly(length)
        return self._serde.deserialize(encoded, self._response_type)

    def __aiter__(self) -> AsyncIterator[T]:
        return self

    def response_headers(self) -> CIMultiDict[str]:
        """Get HTTP response headers from the initial response."""
        return self._response_headers

    def response_trailers(self) -> CIMultiDict[str]:
        if not self._consumed:
            raise RuntimeError("Stream must be fully consumed before accessing trailing metadata")
        return self._response_trailers

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
        await self.close()

    async def close(self) -> None:
        """Explicitly release connection resources.

        Safe to call multiple times. Releases the HTTP connection back to
        the connection pool for reuse.
        """
        if not self._released:
            self._released = True
            await self._response.release()

    def done(self) -> bool:
        return self._consumed

    def error(self) -> ConnectError | None:
        return self._error


class ConnectPartialUnaryResponse(Exception):
    def __init__(self, partial_response: ConnectUnaryOutput[Any]):
        super().__init__("server response was interrupted, partial content received")
        self.partial_response = partial_response


class ConnectProtocolError(ValueError):
    """ConnectProtocolError represents an error in which a client or
    server didn't obey the Connect Protocol Spec.
    """

    pass


class UnexpectedContentType(ConnectProtocolError):
    def __init__(self, content_type: str):
        super().__init__(f"received unexpected content type '{content_type}'")
        self.content_type_received = content_type
