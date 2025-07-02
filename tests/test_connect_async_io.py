"""Tests for Connect protocol async I/O primitives."""

import struct
from unittest.mock import AsyncMock

import pytest

from connectrpc.connect_async_io import AsyncEnvelopeParser
from connectrpc.connect_async_io import EnvelopeData
from connectrpc.connect_compression import GzipCodec
from connectrpc.connect_compression import IdentityCodec
from connectrpc.errors import ConnectError
from connectrpc.errors import ConnectErrorCode
from connectrpc.server_asgi_io import AsyncRequestBodyReader


class TestAsyncEnvelopeParser:
    """Test cases for AsyncEnvelopeParser."""

    @pytest.fixture
    def mock_receive(self):
        """Create a mock ASGI receive callable."""
        return AsyncMock()

    def create_envelope(self, flags: int, data: bytes) -> bytes:
        """Helper to create envelope bytes."""
        return struct.pack(">BI", flags, len(data)) + data

    @pytest.mark.asyncio
    async def test_parse_uncompressed_envelope(self, mock_receive):
        """Test parsing a standard uncompressed envelope."""
        # Setup: create envelope with test data
        test_data = b"Hello, World!"
        envelope_bytes = self.create_envelope(0, test_data)

        # Mock ASGI receive to return the envelope data
        mock_receive.side_effect = [
            {"type": "http.request", "body": envelope_bytes, "more_body": False}
        ]

        # Create parser
        body_reader = AsyncRequestBodyReader(mock_receive)
        parser = AsyncEnvelopeParser(body_reader, IdentityCodec)

        # Parse envelope
        result = await parser.parse_envelope()

        # Verify results
        assert isinstance(result, EnvelopeData)
        assert result.flags == 0
        assert result.data == test_data
        assert result.is_compressed is False
        assert result.is_end_stream is False

    @pytest.mark.asyncio
    async def test_parse_compressed_envelope(self, mock_receive):
        """Test parsing a compressed envelope with gzip."""
        # Setup: create compressed envelope
        test_data = b"Hello, World!"
        compressor = GzipCodec.compressor()
        compressed_data = compressor.compress(test_data) + compressor.flush()
        envelope_bytes = self.create_envelope(0x01, compressed_data)  # 0x01 = compressed

        # Mock ASGI receive
        mock_receive.side_effect = [
            {"type": "http.request", "body": envelope_bytes, "more_body": False}
        ]

        # Create parser with gzip codec
        body_reader = AsyncRequestBodyReader(mock_receive)
        parser = AsyncEnvelopeParser(body_reader, GzipCodec)

        # Parse envelope
        result = await parser.parse_envelope()

        # Verify results
        assert result.flags == 0x01
        assert result.data == test_data  # Should be decompressed
        assert result.is_compressed is True
        assert result.is_end_stream is False

    @pytest.mark.asyncio
    async def test_parse_end_stream_envelope(self, mock_receive):
        """Test parsing an end-stream envelope."""
        # Setup: create end-stream envelope
        test_data = b'{"error":null}'
        envelope_bytes = self.create_envelope(0x02, test_data)  # 0x02 = end-stream

        # Mock ASGI receive
        mock_receive.side_effect = [
            {"type": "http.request", "body": envelope_bytes, "more_body": False}
        ]

        # Create parser
        body_reader = AsyncRequestBodyReader(mock_receive)
        parser = AsyncEnvelopeParser(body_reader, IdentityCodec)

        # Parse envelope
        result = await parser.parse_envelope()

        # Verify results
        assert result.flags == 0x02
        assert result.data == test_data
        assert result.is_compressed is False
        assert result.is_end_stream is True

    @pytest.mark.asyncio
    async def test_parse_compressed_end_stream_envelope(self, mock_receive):
        """Test parsing a compressed end-stream envelope."""
        # Setup: create compressed end-stream envelope
        test_data = b'{"error":null}'
        compressor = GzipCodec.compressor()
        compressed_data = compressor.compress(test_data) + compressor.flush()
        envelope_bytes = self.create_envelope(
            0x03, compressed_data
        )  # 0x03 = compressed + end-stream

        # Mock ASGI receive
        mock_receive.side_effect = [
            {"type": "http.request", "body": envelope_bytes, "more_body": False}
        ]

        # Create parser with gzip codec
        body_reader = AsyncRequestBodyReader(mock_receive)
        parser = AsyncEnvelopeParser(body_reader, GzipCodec)

        # Parse envelope
        result = await parser.parse_envelope()

        # Verify results
        assert result.flags == 0x03
        assert result.data == test_data  # Should be decompressed
        assert result.is_compressed is True
        assert result.is_end_stream is True

    @pytest.mark.asyncio
    async def test_parse_empty_envelope(self, mock_receive):
        """Test parsing an envelope with empty data."""
        # Setup: create empty envelope
        envelope_bytes = self.create_envelope(0, b"")

        # Mock ASGI receive
        mock_receive.side_effect = [
            {"type": "http.request", "body": envelope_bytes, "more_body": False}
        ]

        # Create parser
        body_reader = AsyncRequestBodyReader(mock_receive)
        parser = AsyncEnvelopeParser(body_reader, IdentityCodec)

        # Parse envelope
        result = await parser.parse_envelope()

        # Verify results
        assert result.flags == 0
        assert result.data == b""
        assert result.is_compressed is False
        assert result.is_end_stream is False

    @pytest.mark.asyncio
    async def test_parse_large_envelope(self, mock_receive):
        """Test parsing a large envelope (within limits)."""
        # Setup: create large envelope (1MB)
        test_data = b"x" * (1024 * 1024)
        envelope_bytes = self.create_envelope(0, test_data)

        # Mock ASGI receive
        mock_receive.side_effect = [
            {"type": "http.request", "body": envelope_bytes, "more_body": False}
        ]

        # Create parser
        body_reader = AsyncRequestBodyReader(mock_receive)
        parser = AsyncEnvelopeParser(body_reader, IdentityCodec)

        # Parse envelope
        result = await parser.parse_envelope()

        # Verify results
        assert result.flags == 0
        assert result.data == test_data
        assert len(result.data) == 1024 * 1024

    @pytest.mark.asyncio
    async def test_parse_envelope_across_multiple_events(self, mock_receive):
        """Test parsing an envelope that spans multiple ASGI events."""
        # Setup: create envelope and split across events
        test_data = b"Hello, World!"
        envelope_bytes = self.create_envelope(0, test_data)

        # Split envelope across multiple events
        mid_point = len(envelope_bytes) // 2
        first_chunk = envelope_bytes[:mid_point]
        second_chunk = envelope_bytes[mid_point:]

        # Mock ASGI receive
        mock_receive.side_effect = [
            {"type": "http.request", "body": first_chunk, "more_body": True},
            {"type": "http.request", "body": second_chunk, "more_body": False},
        ]

        # Create parser
        body_reader = AsyncRequestBodyReader(mock_receive)
        parser = AsyncEnvelopeParser(body_reader, IdentityCodec)

        # Parse envelope
        result = await parser.parse_envelope()

        # Verify results
        assert result.flags == 0
        assert result.data == test_data

    @pytest.mark.asyncio
    async def test_eof_during_header_read(self, mock_receive):
        """Test EOFError when stream ends during header read."""
        # Setup: incomplete header (only 3 bytes instead of 5)
        incomplete_header = b"abc"

        # Mock ASGI receive
        mock_receive.side_effect = [
            {"type": "http.request", "body": incomplete_header, "more_body": False}
        ]

        # Create parser
        body_reader = AsyncRequestBodyReader(mock_receive)
        parser = AsyncEnvelopeParser(body_reader, IdentityCodec)

        # Parse envelope should raise EOFError
        with pytest.raises(EOFError):
            await parser.parse_envelope()

    @pytest.mark.asyncio
    async def test_eof_during_data_read(self, mock_receive):
        """Test ConnectError when stream ends during data read."""
        # Setup: complete header but incomplete data
        header_bytes = struct.pack(">BI", 0, 100)  # Claims 100 bytes of data
        incomplete_data = b"only_10_bytes"  # But only provide 13 bytes

        # Mock ASGI receive
        mock_receive.side_effect = [
            {"type": "http.request", "body": header_bytes + incomplete_data, "more_body": False}
        ]

        # Create parser
        body_reader = AsyncRequestBodyReader(mock_receive)
        parser = AsyncEnvelopeParser(body_reader, IdentityCodec)

        # Parse envelope should raise ConnectError
        with pytest.raises(ConnectError) as exc_info:
            await parser.parse_envelope()

        assert exc_info.value.code == ConnectErrorCode.INVALID_ARGUMENT
        assert "Incomplete envelope" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_malformed_envelope_header(self, mock_receive):
        """Test ConnectError for malformed envelope header."""
        # Setup: malformed header (not enough bytes to unpack)
        malformed_header = b"abc"  # Only 3 bytes instead of 5

        # Mock ASGI receive - but make it look like complete data
        mock_receive.side_effect = [
            {"type": "http.request", "body": malformed_header, "more_body": False}
        ]

        # Create parser
        body_reader = AsyncRequestBodyReader(mock_receive)
        parser = AsyncEnvelopeParser(body_reader, IdentityCodec)

        # This will first fail with EOFError trying to read 5 bytes
        with pytest.raises(EOFError):
            await parser.parse_envelope()

    @pytest.mark.asyncio
    async def test_message_too_large(self, mock_receive):
        """Test ConnectError for oversized message length."""
        # Setup: envelope claiming extremely large message (over 64MB limit)
        oversized_length = 128 * 1024 * 1024  # 128MB
        header_bytes = struct.pack(">BI", 0, oversized_length)

        # Mock ASGI receive
        mock_receive.side_effect = [
            {"type": "http.request", "body": header_bytes, "more_body": False}
        ]

        # Create parser
        body_reader = AsyncRequestBodyReader(mock_receive)
        parser = AsyncEnvelopeParser(body_reader, IdentityCodec)

        # Parse envelope should raise ConnectError
        with pytest.raises(ConnectError) as exc_info:
            await parser.parse_envelope()

        assert exc_info.value.code == ConnectErrorCode.INVALID_ARGUMENT
        assert "Message length too large" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_compressed_message_without_compression_codec(self, mock_receive):
        """Test ConnectError when receiving compressed message but no compression specified."""
        # Setup: compressed envelope but using identity codec
        test_data = b"Hello, World!"
        envelope_bytes = self.create_envelope(0x01, test_data)  # 0x01 = compressed flag

        # Mock ASGI receive
        mock_receive.side_effect = [
            {"type": "http.request", "body": envelope_bytes, "more_body": False}
        ]

        # Create parser with identity codec (no compression)
        body_reader = AsyncRequestBodyReader(mock_receive)
        parser = AsyncEnvelopeParser(body_reader, IdentityCodec)

        # Parse envelope should raise ConnectError
        with pytest.raises(ConnectError) as exc_info:
            await parser.parse_envelope()

        assert exc_info.value.code == ConnectErrorCode.INTERNAL
        assert "compressed message but no compression was specified" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_decompression_failure(self, mock_receive):
        """Test ConnectError when decompression fails."""
        # Setup: envelope marked as compressed but with invalid compressed data
        invalid_compressed_data = b"not_actually_gzipped_data"
        envelope_bytes = self.create_envelope(0x01, invalid_compressed_data)

        # Mock ASGI receive
        mock_receive.side_effect = [
            {"type": "http.request", "body": envelope_bytes, "more_body": False}
        ]

        # Create parser with gzip codec
        body_reader = AsyncRequestBodyReader(mock_receive)
        parser = AsyncEnvelopeParser(body_reader, GzipCodec)

        # Parse envelope should raise ConnectError
        with pytest.raises(ConnectError) as exc_info:
            await parser.parse_envelope()

        assert exc_info.value.code == ConnectErrorCode.INVALID_ARGUMENT
        assert "Failed to decompress message" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_uncompressed_message_with_compression_codec(self, mock_receive):
        """Test handling uncompressed message when compression codec is available."""
        # Setup: uncompressed envelope but using gzip codec
        test_data = b"Hello, World!"
        envelope_bytes = self.create_envelope(0, test_data)  # 0 = no compression flag

        # Mock ASGI receive
        mock_receive.side_effect = [
            {"type": "http.request", "body": envelope_bytes, "more_body": False}
        ]

        # Create parser with gzip codec
        body_reader = AsyncRequestBodyReader(mock_receive)
        parser = AsyncEnvelopeParser(body_reader, GzipCodec)

        # Parse envelope should succeed (uncompressed messages allowed)
        result = await parser.parse_envelope()

        # Verify results
        assert result.flags == 0
        assert result.data == test_data  # Should remain uncompressed
        assert result.is_compressed is False

    @pytest.mark.asyncio
    async def test_connection_error_during_parsing(self, mock_receive):
        """Test handling of connection errors during parsing."""
        # Mock ASGI receive to simulate disconnect
        mock_receive.side_effect = [{"type": "http.disconnect"}]

        # Create parser
        body_reader = AsyncRequestBodyReader(mock_receive)
        parser = AsyncEnvelopeParser(body_reader, IdentityCodec)

        # Parse envelope should raise ConnectionError
        with pytest.raises(ConnectionError):
            await parser.parse_envelope()

    @pytest.mark.asyncio
    async def test_multiple_compressed_envelopes(self, mock_receive):
        """Test parsing multiple compressed envelopes sequentially."""
        # Setup: two compressed envelopes (each message compressed individually)
        test_data1 = b"First message"
        test_data2 = b"Second message"

        compressor1 = GzipCodec.compressor()
        compressed_data1 = compressor1.compress(test_data1) + compressor1.flush()
        envelope1 = self.create_envelope(0x01, compressed_data1)

        compressor2 = GzipCodec.compressor()
        compressed_data2 = compressor2.compress(test_data2) + compressor2.flush()
        envelope2 = self.create_envelope(0x01, compressed_data2)

        # Mock ASGI receive for both envelopes
        mock_receive.side_effect = [
            {"type": "http.request", "body": envelope1, "more_body": True},
            {"type": "http.request", "body": envelope2, "more_body": False},
        ]

        # Create parser
        body_reader = AsyncRequestBodyReader(mock_receive)
        parser = AsyncEnvelopeParser(body_reader, GzipCodec)

        # Parse first envelope
        result1 = await parser.parse_envelope()
        assert result1.data == test_data1
        assert result1.is_compressed is True

        # Parse second envelope (each message uses new decompressor)
        result2 = await parser.parse_envelope()
        assert result2.data == test_data2
        assert result2.is_compressed is True
