"""Async I/O primitives for Connect protocol.

This module provides async versions of Connect protocol I/O operations
that work with ASGI receive events instead of sync file-like objects.

"""

import struct
from typing import NamedTuple

from connectrpc.connect_compression import CompressionCodec
from connectrpc.connect_compression import IdentityCodec
from connectrpc.errors import ConnectError
from connectrpc.errors import ConnectErrorCode
from connectrpc.server_asgi_io import AsyncRequestBodyReader


class EnvelopeData(NamedTuple):
    """Data parsed from a Connect protocol envelope.

    Contains the envelope flags, message data, and metadata about
    the envelope type and compression status.
    """

    flags: int
    data: bytes
    is_compressed: bool
    is_end_stream: bool


class AsyncEnvelopeParser:
    """Async envelope parser for Connect protocol's streaming message format.

    Connect streaming uses length-delimited envelopes with the format:
    [1 byte flags][4 bytes big-endian length][data]

    Envelope flags:
    - 0x01: Message is compressed
    - 0x02: End-stream message (contains EndStreamResponse)

    This parser works with ASGI receive events through AsyncRequestBodyReader
    and handles compression integration with existing compression codecs.
    """

    def __init__(
        self,
        body_reader: AsyncRequestBodyReader,
        compression_codec: CompressionCodec = IdentityCodec,
    ):
        """Initialize the async envelope parser.

        Args:
            body_reader: AsyncRequestBodyReader for reading from ASGI receive events
            compression_codec: Compression codec for handling compressed messages
        """
        self._body_reader = body_reader
        self._compression_codec = compression_codec

    async def parse_envelope(self) -> EnvelopeData:
        """Parse a single envelope from the stream.

        Reads the 5-byte envelope header, then reads the message data.
        Handles compression flags and creates appropriate decompressor if needed.

        Returns:
            EnvelopeData containing the parsed envelope information

        Raises:
            EOFError: If stream ends before complete envelope is read
            ConnectError: If envelope is malformed or compression mismatch
            ConnectionError: If client disconnects during reading
        """
        try:
            # Read the 5-byte envelope header: [1 byte flags][4 bytes length]
            envelope_header = await self._body_reader.read_exactly(5)
        except EOFError:
            # End of stream - this is normal for stream termination
            raise

        # Parse the envelope header
        try:
            envelope_flags, message_length = struct.unpack(">BI", envelope_header)
        except struct.error as e:
            raise ConnectError(
                ConnectErrorCode.INVALID_ARGUMENT, f"Malformed envelope header: {e}"
            ) from e

        # Validate message length is reasonable (prevent DoS)
        if message_length > 64 * 1024 * 1024:  # 64MB limit
            raise ConnectError(
                ConnectErrorCode.INVALID_ARGUMENT,
                f"Message length too large: {message_length} bytes",
            )

        # Read the message data
        try:
            if message_length > 0:
                message_data = await self._body_reader.read_exactly(message_length)
            else:
                message_data = b""
        except EOFError as e:
            raise ConnectError(
                ConnectErrorCode.INVALID_ARGUMENT,
                f"Incomplete envelope: expected {message_length} bytes but stream ended",
            ) from e

        # Parse envelope flags
        is_compressed = bool(envelope_flags & 0x01)
        is_end_stream = bool(envelope_flags & 0x02)

        # Handle compression
        if is_compressed:
            # Validate that compression is expected
            if self._compression_codec.label == "identity":
                raise ConnectError(
                    ConnectErrorCode.INTERNAL,
                    "Received compressed message but no compression was specified in headers",
                )

            # Create a new decompressor for each compressed message
            # (Connect protocol compresses each message individually)
            decompressor = self._compression_codec.decompressor()

            # Decompress the message data
            try:
                message_data = decompressor.decompress(message_data)
            except Exception as e:
                raise ConnectError(
                    ConnectErrorCode.INVALID_ARGUMENT, f"Failed to decompress message: {e}"
                ) from e

        elif self._compression_codec.label != "identity":
            # No compression flag but compression was specified in headers
            # This might be OK - some implementations send uncompressed messages
            # even when compression is available
            pass

        return EnvelopeData(
            flags=envelope_flags,
            data=message_data,
            is_compressed=is_compressed,
            is_end_stream=is_end_stream,
        )
