"""ASGI streaming support for ConnectRPC server implementation.

This module provides async streaming classes for handling streaming RPCs
with ASGI's event-driven model, including client streams and response
handling for all streaming RPC types.

"""

from __future__ import annotations

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
from .server_asgi_io import AsyncRequestBodyReader
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

        # Check timeout before reading each message
        self.timeout.check()

        try:
            # Parse the next envelope from the stream
            envelope_data = await self._envelope_parser.parse_envelope()
        except EOFError:
            # Normal end of stream
            self._ended = True
            raise StopAsyncIteration from None

        # Handle end-stream envelope
        if envelope_data.is_end_stream:
            self._ended = True
            # End-stream envelopes contain EndStreamResponse, not user messages
            raise StopAsyncIteration

        # Deserialize the message data
        try:
            message = self._serialization.deserialize(envelope_data.data, self._msg_type)
        except Exception as e:
            raise ConnectError(
                ConnectErrorCode.INVALID_ARGUMENT,
                f"Failed to deserialize message: {e}",
            ) from e

        return message
