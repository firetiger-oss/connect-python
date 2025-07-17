"""ASGI streaming support for ConnectRPC server implementation.

This module provides async streaming classes for handling streaming RPCs
with ASGI's event-driven model, including client streams and response
handling for all streaming RPC types.

"""

from __future__ import annotations

import struct
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING
from typing import Generic
from typing import TypeVar

from google.protobuf.message import Message
from multidict import CIMultiDict

from .connect_async_io import AsyncEnvelopeParser
from .connect_compression import CompressionCodec
from .connect_serialization import ConnectSerialization
from .errors import ConnectError
from .errors import ConnectErrorCode
from .server_asgi_io import ASGIResponse
from .server_asgi_io import AsyncRequestBodyReader
from .streams_connect import EndStreamResponse
from .timeouts import ConnectTimeout

if TYPE_CHECKING:
    pass

T = TypeVar("T", bound=Message)


class AsyncClientStream(Generic[T]):
    """Represents a streaming request from a client to a RPC method on the server.

    This is the async equivalent of ClientStream[T] that users interact with in
    streaming RPC handlers. It provides an async iterator interface over incoming
    client messages while handling the Connect envelope protocol.

    Used for:
    - Client streaming RPCs: AsyncClientStream[T] → ServerResponse[U]
    - Bidirectional streaming RPCs: AsyncClientStream[T] → AsyncIterator[U]
    """

    def __init__(
        self,
        envelope_parser: AsyncEnvelopeParser,
        serialization: ConnectSerialization,
        msg_type: type[T],
        headers: CIMultiDict[str],
        timeout: ConnectTimeout,
    ):
        """Initialize the async client stream.

        Args:
            envelope_parser: AsyncEnvelopeParser for reading Connect protocol envelopes
            serialization: Serialization codec for deserializing messages
            msg_type: The protobuf message type for deserialization
            headers: Request headers from the client
            timeout: Request timeout for deadline checking
        """
        self._envelope_parser = envelope_parser
        self._serialization = serialization
        self._msg_type = msg_type
        self.headers = headers
        self.timeout = timeout
        self._ended = False

    @classmethod
    async def from_asgi_request(
        cls,
        body_reader: AsyncRequestBodyReader,
        serialization: ConnectSerialization,
        compression_codec: CompressionCodec,
        msg_type: type[T],
        headers: CIMultiDict[str],
        timeout: ConnectTimeout,
    ) -> AsyncClientStream[T]:
        """Create AsyncClientStream from ASGI request components.

        Args:
            body_reader: AsyncRequestBodyReader for reading from ASGI receive events
            serialization: Serialization codec for messages
            compression_codec: Compression codec for handling compressed messages
            msg_type: The protobuf message type for deserialization
            headers: Request headers from client
            timeout: Request timeout for deadline checking

        Returns:
            AsyncClientStream instance ready for async iteration
        """
        envelope_parser = AsyncEnvelopeParser(body_reader, compression_codec)

        return cls(
            envelope_parser=envelope_parser,
            serialization=serialization,
            msg_type=msg_type,
            headers=headers,
            timeout=timeout,
        )

    def __aiter__(self) -> AsyncIterator[T]:
        """Return self as async iterator."""
        return self

    async def __anext__(self) -> T:
        """Get the next message from the client stream.

        Returns:
            The next deserialized message from the client

        Raises:
            StopAsyncIteration: When the stream ends normally
            ConnectError: For protocol violations or malformed messages
            EOFError: If connection is lost unexpectedly
        """
        if self._ended:
            raise StopAsyncIteration

        self.timeout.check()

        try:
            envelope_data = await self._envelope_parser.parse_envelope()
        except EOFError:
            self._ended = True
            raise StopAsyncIteration from None

        if envelope_data.is_end_stream:
            self._ended = True
            raise StopAsyncIteration

        try:
            message = self._serialization.deserialize(envelope_data.data, self._msg_type)
        except Exception as e:
            raise ConnectError(
                ConnectErrorCode.INVALID_ARGUMENT,
                f"Failed to deserialize message: {e}",
            ) from e

        return message


class AsyncStreamingResponseSender(Generic[T]):
    """Handles sending streaming responses via ASGI events using Connect envelope protocol.

    This class takes an async iterator from user handlers and sends the messages via ASGI
    events using Connect's envelope protocol. Supports both server streaming and
    bidirectional streaming response patterns.

    Used for:
    - Server streaming RPCs: unary request → AsyncIterator[U] response
    - Bidirectional streaming RPCs: AsyncClientStream[T] → AsyncIterator[U] response
    """

    def __init__(
        self,
        response: ASGIResponse,
        serialization: ConnectSerialization,
        compression_codec: CompressionCodec,
    ):
        """Initialize the streaming response sender.

        Args:
            response: ASGIResponse for sending via ASGI events
            serialization: Serialization codec for messages
            compression_codec: Compression codec for message compression
            msg_type: The protobuf message type for serialization
        """
        self._response = response
        self._serialization = serialization
        self._compression_codec = compression_codec
        self._started = False
        self._finished = False

    async def send_stream(
        self,
        message_iterator: AsyncIterator[T],
        headers: list[tuple[bytes, bytes]],
        trailers: CIMultiDict[str] | None = None,
    ) -> None:
        """Send a streaming response by iterating over the message iterator.

        Args:
            message_iterator: Async iterator of response messages from user handler
            headers: HTTP headers to send with the response
            trailers: Optional trailing metadata

        Raises:
            ConnectError: If message serialization fails
            ConnectionError: If client disconnects during streaming
            RuntimeError: If response is already started or finished
        """
        if self._started:
            raise RuntimeError("Streaming response has already been started")
        if self._finished:
            raise RuntimeError("Streaming response has already been finished")

        await self._response.send_start(status=200, headers=headers, trailers=trailers is not None)
        self._started = True

        try:
            async for message in message_iterator:
                await self._send_message_envelope(message, is_end_stream=False)
        except ConnectError as e:
            await self._send_end_stream(error=e, metadata=trailers)
            raise
        except Exception as e:
            error = ConnectError(ConnectErrorCode.INTERNAL, f"Error during response streaming: {e}")
            await self._send_end_stream(error=error, metadata=trailers)
            raise
        else:
            await self._send_end_stream(error=None, metadata=trailers)
        finally:
            self._finished = True

    async def _send_message_envelope(self, message: T, is_end_stream: bool) -> None:
        """Send a single message in Connect envelope format.

        Args:
            message: The message to serialize and send
            is_end_stream: Whether this is an end-stream envelope

        Raises:
            ConnectError: If message serialization fails
            ConnectionError: If sending fails
        """
        try:
            message_data = self._serialization.serialize(message)
        except Exception as e:
            raise ConnectError(
                ConnectErrorCode.INTERNAL, f"Failed to serialize response message: {e}"
            ) from e

        envelope_flags = 0
        if self._compression_codec.label != "identity":
            try:
                compressor = self._compression_codec.compressor()
                message_data = compressor.compress(message_data) + compressor.flush()
                envelope_flags |= 0x01  # Set compression flag
            except Exception as e:
                raise ConnectError(
                    ConnectErrorCode.INTERNAL, f"Failed to compress response message: {e}"
                ) from e

        if is_end_stream:
            envelope_flags |= 0x02

        envelope_header = struct.pack(">BI", envelope_flags, len(message_data))
        envelope_data = envelope_header + message_data

        await self._response.send_body(envelope_data, more_body=True)

    async def _send_end_stream(
        self, error: ConnectError | None, metadata: CIMultiDict[str] | None
    ) -> None:
        """Send end-stream envelope with EndStreamResponse.

        Args:
            error: Optional error for end-stream
            metadata: Optional trailing metadata

        Raises:
            ConnectionError: If sending fails
        """
        end_stream_metadata = metadata or CIMultiDict()
        end_stream_response = EndStreamResponse(error=error, metadata=end_stream_metadata)

        end_stream_data = end_stream_response.to_json()

        envelope_flags = 0x02
        if self._compression_codec.label != "identity":
            try:
                compressor = self._compression_codec.compressor()
                end_stream_data = compressor.compress(end_stream_data) + compressor.flush()
                envelope_flags |= 0x01
            except Exception:
                # Compression failure for end-stream is not critical.
                # Fall back to uncompressed
                pass

        envelope_header = struct.pack(">BI", envelope_flags, len(end_stream_data))
        envelope_data = envelope_header + end_stream_data

        await self._response.send_body(envelope_data, more_body=False)
