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
from connectrpc.server_asgi_io import ASGIResponse
from connectrpc.server_asgi_io import AsyncRequestBodyReader
from connectrpc.server_asgi_streams import AsyncClientStream
from connectrpc.server_asgi_streams import AsyncStreamingResponseSender
from connectrpc.streams_connect import EndStreamResponse
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


class MockSend:
    """Mock ASGI send callable for testing."""

    def __init__(self):
        self.events = []

    async def __call__(self, message):
        self.events.append(message)

    def get_start_event(self):
        """Get the http.response.start event."""
        for event in self.events:
            if event["type"] == "http.response.start":
                return event
        return None

    def get_body_events(self):
        """Get all http.response.body events."""
        return [event for event in self.events if event["type"] == "http.response.body"]

    def get_trailer_events(self):
        """Get all http.response.trailers events."""
        return [event for event in self.events if event["type"] == "http.response.trailers"]


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


class TestAsyncStreamingResponseSender:
    """Tests for AsyncStreamingResponseSender class."""

    @pytest.mark.asyncio
    async def test_send_single_message_stream(self):
        """Test sending a single message response stream."""
        mock_send = MockSend()
        response = ASGIResponse(mock_send)

        sender = AsyncStreamingResponseSender(
            response=response,
            serialization=CONNECT_PROTOBUF_SERIALIZATION,
            compression_codec=IdentityCodec,
            msg_type=StringValue,
        )

        # Create a simple async iterator
        async def simple_stream():
            yield StringValue(value="hello")

        headers = [(b"content-type", b"application/connect+proto")]
        await sender.send_stream(simple_stream(), headers)

        # Verify events
        start_event = mock_send.get_start_event()
        assert start_event is not None
        assert start_event["status"] == 200
        assert start_event["headers"] == headers

        body_events = mock_send.get_body_events()
        assert len(body_events) == 2  # One for message, one for end-stream

        # Parse first envelope (message)
        first_body = body_events[0]["body"]
        message_flags, message_length = struct.unpack(">BI", first_body[:5])
        assert message_flags == 0  # No compression, no end-stream
        message_data = first_body[5 : 5 + message_length]

        # Deserialize and verify
        parsed_msg = CONNECT_PROTOBUF_SERIALIZATION.deserialize(message_data, StringValue)
        assert parsed_msg.value == "hello"

        # Parse second envelope (end-stream)
        second_body = body_events[1]["body"]
        end_flags, end_length = struct.unpack(">BI", second_body[:5])
        assert end_flags == 2  # End-stream flag
        end_data = second_body[5 : 5 + end_length]

        # Verify end-stream response
        end_response = EndStreamResponse.from_bytes(end_data)
        assert end_response.error is None

    @pytest.mark.asyncio
    async def test_send_multiple_message_stream(self):
        """Test sending multiple message response stream."""
        mock_send = MockSend()
        response = ASGIResponse(mock_send)

        sender = AsyncStreamingResponseSender(
            response=response,
            serialization=CONNECT_PROTOBUF_SERIALIZATION,
            compression_codec=IdentityCodec,
            msg_type=StringValue,
        )

        # Create async iterator with multiple messages
        async def multi_stream():
            yield StringValue(value="first")
            yield StringValue(value="second")
            yield StringValue(value="third")

        headers = [(b"content-type", b"application/connect+proto")]
        await sender.send_stream(multi_stream(), headers)

        body_events = mock_send.get_body_events()
        assert len(body_events) == 4  # Three messages + end-stream

        # Verify each message envelope
        messages = []
        for i in range(3):  # First 3 are messages
            body = body_events[i]["body"]
            flags, length = struct.unpack(">BI", body[:5])
            assert flags == 0  # No compression, no end-stream
            data = body[5 : 5 + length]
            msg = CONNECT_PROTOBUF_SERIALIZATION.deserialize(data, StringValue)
            messages.append(msg.value)

        assert messages == ["first", "second", "third"]

        # Verify end-stream
        end_body = body_events[3]["body"]
        end_flags, end_length = struct.unpack(">BI", end_body[:5])
        assert end_flags == 2  # End-stream flag

    @pytest.mark.asyncio
    async def test_send_empty_stream(self):
        """Test sending empty response stream (only end-stream)."""
        mock_send = MockSend()
        response = ASGIResponse(mock_send)

        sender = AsyncStreamingResponseSender(
            response=response,
            serialization=CONNECT_PROTOBUF_SERIALIZATION,
            compression_codec=IdentityCodec,
            msg_type=StringValue,
        )

        # Create empty async iterator
        async def empty_stream():
            return
            yield  # Never reached

        headers = [(b"content-type", b"application/connect+proto")]
        await sender.send_stream(empty_stream(), headers)

        body_events = mock_send.get_body_events()
        assert len(body_events) == 1  # Only end-stream

        # Verify end-stream
        end_body = body_events[0]["body"]
        end_flags, end_length = struct.unpack(">BI", end_body[:5])
        assert end_flags == 2  # End-stream flag

    @pytest.mark.asyncio
    async def test_stream_with_error(self):
        """Test handling of errors during streaming."""
        mock_send = MockSend()
        response = ASGIResponse(mock_send)

        sender = AsyncStreamingResponseSender(
            response=response,
            serialization=CONNECT_PROTOBUF_SERIALIZATION,
            compression_codec=IdentityCodec,
            msg_type=StringValue,
        )

        # Create async iterator that raises an error
        async def error_stream():
            yield StringValue(value="before_error")
            raise ValueError("Stream error!")

        headers = [(b"content-type", b"application/connect+proto")]

        with pytest.raises(ValueError) as exc_info:
            await sender.send_stream(error_stream(), headers)

        assert "Stream error!" in str(exc_info.value)

        body_events = mock_send.get_body_events()
        assert len(body_events) == 2  # Message + error end-stream

        # Verify message was sent before error
        msg_body = body_events[0]["body"]
        msg_flags, msg_length = struct.unpack(">BI", msg_body[:5])
        assert msg_flags == 0
        msg_data = msg_body[5 : 5 + msg_length]
        msg = CONNECT_PROTOBUF_SERIALIZATION.deserialize(msg_data, StringValue)
        assert msg.value == "before_error"

        # Verify error end-stream
        end_body = body_events[1]["body"]
        end_flags, end_length = struct.unpack(">BI", end_body[:5])
        assert end_flags == 2  # End-stream flag
        end_data = end_body[5 : 5 + end_length]
        end_response = EndStreamResponse.from_bytes(end_data)
        assert end_response.error is not None
        assert end_response.error.code == ConnectErrorCode.INTERNAL

    @pytest.mark.asyncio
    async def test_stream_with_trailers(self):
        """Test sending stream with trailing metadata."""
        mock_send = MockSend()
        response = ASGIResponse(mock_send)

        sender = AsyncStreamingResponseSender(
            response=response,
            serialization=CONNECT_PROTOBUF_SERIALIZATION,
            compression_codec=IdentityCodec,
            msg_type=StringValue,
        )

        async def simple_stream():
            yield StringValue(value="with_trailers")

        headers = [(b"content-type", b"application/connect+proto")]
        trailers = CIMultiDict()
        trailers["custom-trailer"] = "trailer-value"
        trailers["response-count"] = "1"

        await sender.send_stream(simple_stream(), headers, trailers)

        # Verify trailers are promised in start event
        start_event = mock_send.get_start_event()
        assert start_event["trailers"]

        # Verify end-stream contains trailer metadata
        body_events = mock_send.get_body_events()
        end_body = body_events[1]["body"]  # Second body event is end-stream
        end_flags, end_length = struct.unpack(">BI", end_body[:5])
        end_data = end_body[5 : 5 + end_length]
        end_response = EndStreamResponse.from_bytes(end_data)

        assert "custom-trailer" in end_response.metadata
        assert end_response.metadata["custom-trailer"] == "trailer-value"
        assert end_response.metadata["response-count"] == "1"

    @pytest.mark.asyncio
    async def test_double_start_error(self):
        """Test error when trying to start streaming twice."""
        mock_send = MockSend()
        response = ASGIResponse(mock_send)

        sender = AsyncStreamingResponseSender(
            response=response,
            serialization=CONNECT_PROTOBUF_SERIALIZATION,
            compression_codec=IdentityCodec,
            msg_type=StringValue,
        )

        async def simple_stream():
            yield StringValue(value="test")

        headers = [(b"content-type", b"application/connect+proto")]

        # First call should succeed
        await sender.send_stream(simple_stream(), headers)

        # Second call should fail
        with pytest.raises(RuntimeError) as exc_info:
            await sender.send_stream(simple_stream(), headers)

        assert "already been started" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_large_stream_performance(self):
        """Test performance with large number of messages."""
        mock_send = MockSend()
        response = ASGIResponse(mock_send)

        sender = AsyncStreamingResponseSender(
            response=response,
            serialization=CONNECT_PROTOBUF_SERIALIZATION,
            compression_codec=IdentityCodec,
            msg_type=StringValue,
        )

        # Create stream with many messages
        async def large_stream():
            for i in range(100):
                yield StringValue(value=f"message_{i}")

        headers = [(b"content-type", b"application/connect+proto")]
        await sender.send_stream(large_stream(), headers)

        body_events = mock_send.get_body_events()
        assert len(body_events) == 101  # 100 messages + end-stream

        # Verify messages are correctly formatted
        for i in range(100):
            body = body_events[i]["body"]
            flags, length = struct.unpack(">BI", body[:5])
            assert flags == 0  # No special flags for messages
            data = body[5 : 5 + length]
            msg = CONNECT_PROTOBUF_SERIALIZATION.deserialize(data, StringValue)
            assert msg.value == f"message_{i}"

        # Verify end-stream
        end_body = body_events[100]["body"]
        end_flags, _ = struct.unpack(">BI", end_body[:5])
        assert end_flags == 2  # End-stream flag

    @pytest.mark.asyncio
    async def test_integration_with_asgi_response_lifecycle(self):
        """Integration test demonstrating complete ASGI response lifecycle."""
        mock_send = MockSend()
        response = ASGIResponse(mock_send)

        sender = AsyncStreamingResponseSender(
            response=response,
            serialization=CONNECT_PROTOBUF_SERIALIZATION,
            compression_codec=IdentityCodec,
            msg_type=StringValue,
        )

        # Simulate a realistic server streaming scenario
        async def server_streaming_handler():
            """Simulates a typical server streaming handler."""
            # Initial response
            yield StringValue(value="starting_stream")

            # Simulate some async work
            await asyncio.sleep(0.001)

            # Stream some data
            for i in range(3):
                yield StringValue(value=f"item_{i}")
                await asyncio.sleep(0.001)  # Simulate processing time

            # Final response
            yield StringValue(value="stream_complete")

        # Create realistic headers and trailers
        headers = [
            (b"content-type", b"application/connect+proto"),
            (b"connect-protocol-version", b"1"),
            (b"server", b"connect-python-asgi/1.0"),
        ]

        trailers = CIMultiDict()
        trailers["grpc-status"] = "0"
        trailers["grpc-message"] = ""
        trailers["custom-response-id"] = "12345"

        # Execute the complete streaming response
        await sender.send_stream(server_streaming_handler(), headers, trailers)

        # Verify complete ASGI response lifecycle

        # 1. Verify start event
        start_event = mock_send.get_start_event()
        assert start_event is not None
        assert start_event["status"] == 200
        assert start_event["headers"] == headers
        assert start_event["trailers"]

        # 2. Verify body events (5 messages + 1 end-stream)
        body_events = mock_send.get_body_events()
        assert len(body_events) == 6

        # 3. Verify message content and ordering
        expected_messages = ["starting_stream", "item_0", "item_1", "item_2", "stream_complete"]

        for i, expected_msg in enumerate(expected_messages):
            body = body_events[i]["body"]
            flags, length = struct.unpack(">BI", body[:5])
            assert flags == 0  # Regular message, no special flags
            data = body[5 : 5 + length]
            msg = CONNECT_PROTOBUF_SERIALIZATION.deserialize(data, StringValue)
            assert msg.value == expected_msg
            assert body_events[i]["more_body"]  # More data coming

        # 4. Verify end-stream envelope
        end_body = body_events[5]["body"]
        end_flags, end_length = struct.unpack(">BI", end_body[:5])
        assert end_flags == 2  # End-stream flag
        assert not body_events[5]["more_body"]  # Final chunk

        end_data = end_body[5 : 5 + end_length]
        end_response = EndStreamResponse.from_bytes(end_data)
        assert end_response.error is None

        # 5. Verify trailing metadata
        assert end_response.metadata["grpc-status"] == "0"
        assert end_response.metadata["grpc-message"] == ""
        assert end_response.metadata["custom-response-id"] == "12345"

    @pytest.mark.asyncio
    async def test_bidirectional_streaming_pattern(self):
        """Test pattern that would be used for bidirectional streaming."""
        mock_send = MockSend()
        response = ASGIResponse(mock_send)

        sender = AsyncStreamingResponseSender(
            response=response,
            serialization=CONNECT_PROTOBUF_SERIALIZATION,
            compression_codec=IdentityCodec,
            msg_type=StringValue,
        )

        # Simulate bidirectional streaming where responses are generated
        # based on some input stream (would be AsyncClientStream in real usage)
        simulated_input = ["hello", "world", "test"]

        async def bidirectional_handler():
            """Simulates processing of streaming input to produce streaming output."""
            for input_msg in simulated_input:
                # Simulate processing input message
                processed = f"processed_{input_msg}"
                yield StringValue(value=processed)

                # Simulate async processing time
                await asyncio.sleep(0.001)

                # Could yield multiple responses per input
                confirmation = f"confirmed_{input_msg}"
                yield StringValue(value=confirmation)

        headers = [(b"content-type", b"application/connect+proto")]
        await sender.send_stream(bidirectional_handler(), headers)

        # Verify the bidirectional pattern worked
        body_events = mock_send.get_body_events()
        assert len(body_events) == 7  # 6 responses + 1 end-stream

        expected_responses = [
            "processed_hello",
            "confirmed_hello",
            "processed_world",
            "confirmed_world",
            "processed_test",
            "confirmed_test",
        ]

        for i, expected in enumerate(expected_responses):
            body = body_events[i]["body"]
            flags, length = struct.unpack(">BI", body[:5])
            assert flags == 0
            data = body[5 : 5 + length]
            msg = CONNECT_PROTOBUF_SERIALIZATION.deserialize(data, StringValue)
            assert msg.value == expected

    @pytest.mark.asyncio
    async def test_large_response_stream_performance(self):
        """Performance test for large response streams."""
        import time

        mock_send = MockSend()
        response = ASGIResponse(mock_send)

        sender = AsyncStreamingResponseSender(
            response=response,
            serialization=CONNECT_PROTOBUF_SERIALIZATION,
            compression_codec=IdentityCodec,
            msg_type=StringValue,
        )

        # Generate a large number of messages
        message_count = 1000

        async def large_response_stream():
            """Generate a large number of response messages."""
            for i in range(message_count):
                # Create messages with varying content size
                content = f"large_message_{i}_" + "x" * (i % 100)
                yield StringValue(value=content)

                # Occasional async yield to test performance under async conditions
                if i % 100 == 0:
                    await asyncio.sleep(0)

        headers = [(b"content-type", b"application/connect+proto")]

        # Measure performance
        start_time = time.time()
        await sender.send_stream(large_response_stream(), headers)
        end_time = time.time()

        # Verify all messages were sent
        body_events = mock_send.get_body_events()
        assert len(body_events) == message_count + 1  # All messages + end-stream

        # Performance assertions (should be fast)
        elapsed_time = end_time - start_time
        assert elapsed_time < 1.0  # Should complete in under 1 second

        # Verify messages per second throughput
        messages_per_second = message_count / elapsed_time
        assert messages_per_second > 100  # Should handle at least 100 messages/sec

        # Verify envelope format integrity for a sample of messages
        sample_indices = [0, message_count // 2, message_count - 1]
        for idx in sample_indices:
            body = body_events[idx]["body"]
            flags, length = struct.unpack(">BI", body[:5])
            assert flags == 0  # No special flags for regular messages
            assert length > 0  # Message should have content

            # Verify the message can be deserialized
            data = body[5 : 5 + length]
            msg = CONNECT_PROTOBUF_SERIALIZATION.deserialize(data, StringValue)
            assert msg.value.startswith(f"large_message_{idx}_")

        # Verify end-stream is correctly formatted
        end_body = body_events[message_count]["body"]
        end_flags, _ = struct.unpack(">BI", end_body[:5])
        assert end_flags == 2  # End-stream flag
