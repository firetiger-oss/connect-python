"""Tests for ASGI streaming support."""

from __future__ import annotations

import asyncio
import struct

import pytest
from google.protobuf.wrappers_pb2 import StringValue
from multidict import CIMultiDict

from connectrpc.connect_compression import IdentityCodec
from connectrpc.connect_serialization import CONNECT_PROTOBUF_SERIALIZATION
from connectrpc.errors import ConnectError
from connectrpc.errors import ConnectErrorCode
from connectrpc.server_asgi_io import AsyncRequestBodyReader
from connectrpc.server_asgi_streams import AsyncClientStream
from connectrpc.timeouts import ConnectTimeout


class MockReceive:
    """Mock ASGI receive callable for testing."""

    def __init__(self, events: list[dict]):
        self.events = events
        self.index = 0

    async def __call__(self):
        if self.index >= len(self.events):
            # Simulate connection closed
            raise asyncio.CancelledError("Connection closed")

        event = self.events[self.index]
        self.index += 1
        return event


def create_envelope(flags: int, data: bytes) -> bytes:
    """Create a Connect protocol envelope."""
    return struct.pack(">BI", flags, len(data)) + data


def create_message_envelope(message: StringValue) -> bytes:
    """Create an envelope containing a serialized message."""
    data = CONNECT_PROTOBUF_SERIALIZATION.serialize(message)
    return create_envelope(0, data)


def create_end_stream_envelope() -> bytes:
    """Create an end-stream envelope."""
    # End-stream envelope typically contains EndStreamResponse JSON
    end_data = b'{"metadata":{}}'
    return create_envelope(2, end_data)


class TestAsyncClientStream:
    """Tests for AsyncClientStream class."""

    @pytest.mark.asyncio
    async def test_async_iteration_single_message(self):
        """Test async iteration over a single message."""
        # Create test message
        test_msg = StringValue(value="hello")
        envelope_data = create_message_envelope(test_msg)
        end_envelope = create_end_stream_envelope()

        # Create mock receive events
        events = [
            {"type": "http.request", "body": envelope_data + end_envelope, "more_body": False}
        ]
        receive = MockReceive(events)

        # Create AsyncClientStream
        body_reader = AsyncRequestBodyReader(receive)
        stream = await AsyncClientStream.from_asgi_request(
            body_reader=body_reader,
            serialization=CONNECT_PROTOBUF_SERIALIZATION,
            compression_codec=IdentityCodec,
            msg_type=StringValue,
            headers=CIMultiDict(),
            timeout=ConnectTimeout(30000),
        )

        # Test async iteration
        messages = []
        async for msg in stream:
            messages.append(msg)

        assert len(messages) == 1
        assert messages[0].value == "hello"

    @pytest.mark.asyncio
    async def test_async_iteration_multiple_messages(self):
        """Test async iteration over multiple messages."""
        # Create test messages
        msg1 = StringValue(value="hello")
        msg2 = StringValue(value="world")
        msg3 = StringValue(value="test")

        envelope1 = create_message_envelope(msg1)
        envelope2 = create_message_envelope(msg2)
        envelope3 = create_message_envelope(msg3)
        end_envelope = create_end_stream_envelope()

        # Create mock receive events (split across multiple events)
        events = [
            {"type": "http.request", "body": envelope1 + envelope2, "more_body": True},
            {"type": "http.request", "body": envelope3 + end_envelope, "more_body": False},
        ]
        receive = MockReceive(events)

        # Create AsyncClientStream
        body_reader = AsyncRequestBodyReader(receive)
        stream = await AsyncClientStream.from_asgi_request(
            body_reader=body_reader,
            serialization=CONNECT_PROTOBUF_SERIALIZATION,
            compression_codec=IdentityCodec,
            msg_type=StringValue,
            headers=CIMultiDict(),
            timeout=ConnectTimeout(30000),
        )

        # Test async iteration
        messages = []
        async for msg in stream:
            messages.append(msg)

        assert len(messages) == 3
        assert messages[0].value == "hello"
        assert messages[1].value == "world"
        assert messages[2].value == "test"

    @pytest.mark.asyncio
    async def test_empty_stream(self):
        """Test async iteration over empty stream (only end-stream envelope)."""
        end_envelope = create_end_stream_envelope()

        events = [{"type": "http.request", "body": end_envelope, "more_body": False}]
        receive = MockReceive(events)

        body_reader = AsyncRequestBodyReader(receive)
        stream = await AsyncClientStream.from_asgi_request(
            body_reader=body_reader,
            serialization=CONNECT_PROTOBUF_SERIALIZATION,
            compression_codec=IdentityCodec,
            msg_type=StringValue,
            headers=CIMultiDict(),
            timeout=ConnectTimeout(30000),
        )

        # Test async iteration
        messages = []
        async for msg in stream:
            messages.append(msg)

        assert len(messages) == 0

    @pytest.mark.asyncio
    async def test_connection_disconnect(self):
        """Test handling of connection disconnect during streaming."""
        # Create partial envelope data (incomplete)
        partial_envelope = struct.pack(">BI", 0, 100)  # Claims 100 bytes but no data follows

        events = [
            {"type": "http.request", "body": partial_envelope, "more_body": True},
            {"type": "http.disconnect"},
        ]
        receive = MockReceive(events)

        body_reader = AsyncRequestBodyReader(receive)
        stream = await AsyncClientStream.from_asgi_request(
            body_reader=body_reader,
            serialization=CONNECT_PROTOBUF_SERIALIZATION,
            compression_codec=IdentityCodec,
            msg_type=StringValue,
            headers=CIMultiDict(),
            timeout=ConnectTimeout(30000),
        )

        # Should raise ConnectionError due to client disconnect
        with pytest.raises(ConnectionError) as exc_info:
            async for _ in stream:
                pass

        assert "Client disconnected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_malformed_envelope(self):
        """Test handling of malformed envelope header."""
        # Create malformed envelope (too short header)
        malformed_data = b"abc"  # Only 3 bytes instead of 5

        events = [{"type": "http.request", "body": malformed_data, "more_body": False}]
        receive = MockReceive(events)

        body_reader = AsyncRequestBodyReader(receive)
        stream = await AsyncClientStream.from_asgi_request(
            body_reader=body_reader,
            serialization=CONNECT_PROTOBUF_SERIALIZATION,
            compression_codec=IdentityCodec,
            msg_type=StringValue,
            headers=CIMultiDict(),
            timeout=ConnectTimeout(30000),
        )

        # Should raise StopAsyncIteration due to EOFError from incomplete header
        messages = []
        async for msg in stream:
            messages.append(msg)

        assert len(messages) == 0

    @pytest.mark.asyncio
    async def test_invalid_message_data(self):
        """Test handling of invalid protobuf message data."""
        # Create envelope with invalid protobuf data
        invalid_data = b"not valid protobuf"
        invalid_envelope = create_envelope(0, invalid_data)
        end_envelope = create_end_stream_envelope()

        events = [
            {"type": "http.request", "body": invalid_envelope + end_envelope, "more_body": False}
        ]
        receive = MockReceive(events)

        body_reader = AsyncRequestBodyReader(receive)
        stream = await AsyncClientStream.from_asgi_request(
            body_reader=body_reader,
            serialization=CONNECT_PROTOBUF_SERIALIZATION,
            compression_codec=IdentityCodec,
            msg_type=StringValue,
            headers=CIMultiDict(),
            timeout=ConnectTimeout(30000),
        )

        # Should raise ConnectError due to deserialization failure
        with pytest.raises(ConnectError) as exc_info:
            async for _ in stream:
                pass

        assert exc_info.value.code == ConnectErrorCode.INVALID_ARGUMENT
        assert "Failed to deserialize message" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_headers_and_metadata_access(self):
        """Test access to request headers and metadata."""
        test_msg = StringValue(value="test")
        envelope_data = create_message_envelope(test_msg)
        end_envelope = create_end_stream_envelope()

        events = [
            {"type": "http.request", "body": envelope_data + end_envelope, "more_body": False}
        ]
        receive = MockReceive(events)

        # Create headers
        headers = CIMultiDict()
        headers["content-type"] = "application/connect+proto"
        headers["connect-timeout-ms"] = "30000"
        headers["custom-header"] = "test-value"

        body_reader = AsyncRequestBodyReader(receive)
        stream = await AsyncClientStream.from_asgi_request(
            body_reader=body_reader,
            serialization=CONNECT_PROTOBUF_SERIALIZATION,
            compression_codec=IdentityCodec,
            msg_type=StringValue,
            headers=headers,
            timeout=ConnectTimeout(30000),
        )

        # Verify headers are accessible
        assert stream.headers["content-type"] == "application/connect+proto"
        assert stream.headers["connect-timeout-ms"] == "30000"
        assert stream.headers["custom-header"] == "test-value"

        # Verify timeout is accessible
        assert stream.timeout is not None

    @pytest.mark.asyncio
    async def test_large_message_handling(self):
        """Test handling of large messages within reasonable limits."""
        # Create a large message (but within limits)
        large_value = "x" * 1000  # 1KB string
        test_msg = StringValue(value=large_value)
        envelope_data = create_message_envelope(test_msg)
        end_envelope = create_end_stream_envelope()

        events = [
            {"type": "http.request", "body": envelope_data + end_envelope, "more_body": False}
        ]
        receive = MockReceive(events)

        body_reader = AsyncRequestBodyReader(receive)
        stream = await AsyncClientStream.from_asgi_request(
            body_reader=body_reader,
            serialization=CONNECT_PROTOBUF_SERIALIZATION,
            compression_codec=IdentityCodec,
            msg_type=StringValue,
            headers=CIMultiDict(),
            timeout=ConnectTimeout(30000),
        )

        # Should handle large message correctly
        messages = []
        async for msg in stream:
            messages.append(msg)

        assert len(messages) == 1
        assert messages[0].value == large_value

    @pytest.mark.asyncio
    async def test_stream_reuse_after_completion(self):
        """Test that stream cannot be reused after completion."""
        test_msg = StringValue(value="test")
        envelope_data = create_message_envelope(test_msg)
        end_envelope = create_end_stream_envelope()

        events = [
            {"type": "http.request", "body": envelope_data + end_envelope, "more_body": False}
        ]
        receive = MockReceive(events)

        body_reader = AsyncRequestBodyReader(receive)
        stream = await AsyncClientStream.from_asgi_request(
            body_reader=body_reader,
            serialization=CONNECT_PROTOBUF_SERIALIZATION,
            compression_codec=IdentityCodec,
            msg_type=StringValue,
            headers=CIMultiDict(),
            timeout=ConnectTimeout(30000),
        )

        # Consume the stream
        messages = []
        async for msg in stream:
            messages.append(msg)

        assert len(messages) == 1

        # Try to iterate again - should be empty
        messages2 = []
        async for msg in stream:
            messages2.append(msg)

        assert len(messages2) == 0

    @pytest.mark.asyncio
    async def test_integration_with_real_asgi_app(self):
        """Integration test demonstrating AsyncClientStream works with real ASGI applications."""
        # This test verifies that AsyncClientStream can be integrated into a real ASGI application
        # For now, we'll simulate a realistic ASGI scenario

        # Create messages that would come from a real Connect client
        msg1 = StringValue(value="integration")
        msg2 = StringValue(value="test")

        envelope1 = create_message_envelope(msg1)
        envelope2 = create_message_envelope(msg2)
        end_envelope = create_end_stream_envelope()

        # Simulate realistic ASGI events from a real server
        events = [
            {"type": "http.request", "body": envelope1, "more_body": True},
            {"type": "http.request", "body": envelope2, "more_body": True},
            {"type": "http.request", "body": end_envelope, "more_body": False},
        ]
        receive = MockReceive(events)

        # Create stream with realistic headers (as would come from a Connect client)
        headers = CIMultiDict()
        headers["content-type"] = "application/connect+proto"
        headers["connect-protocol-version"] = "1"
        headers["user-agent"] = "connect-python/1.0.0"

        body_reader = AsyncRequestBodyReader(receive)
        stream = await AsyncClientStream.from_asgi_request(
            body_reader=body_reader,
            serialization=CONNECT_PROTOBUF_SERIALIZATION,
            compression_codec=IdentityCodec,
            msg_type=StringValue,
            headers=headers,
            timeout=ConnectTimeout(30000),
        )

        # Verify the stream works as expected in an integration scenario
        processed_messages = []
        async for msg in stream:
            # Simulate processing that a real handler might do
            processed_msg = f"processed: {msg.value}"
            processed_messages.append(processed_msg)

        assert len(processed_messages) == 2
        assert processed_messages[0] == "processed: integration"
        assert processed_messages[1] == "processed: test"

        # Verify headers are available for handler logic
        assert stream.headers["content-type"] == "application/connect+proto"
        assert stream.headers["connect-protocol-version"] == "1"
