"""
Tests for ASGI I/O primitives in ConnectRPC server implementation.

This module tests the AsyncRequestBodyReader class that handles ASGI http.request events.
"""

from typing import Any

import pytest

from connectrpc.errors import ConnectError
from connectrpc.server_asgi_io import AsyncRequestBodyReader
from connectrpc.server_asgi_io import AsyncResponseSender


class MockASGIReceive:
    """Mock ASGI receive callable for testing."""

    def __init__(self, events: list[dict[str, Any]]):
        """
        Initialize with a list of ASGI events to return.

        Args:
            events: List of ASGI event dictionaries
        """
        self.events = events
        self.index = 0

    async def __call__(self) -> dict[str, Any]:
        """Return the next event or raise if no more events."""
        if self.index >= len(self.events):
            raise RuntimeError("No more events available")

        event = self.events[self.index]
        self.index += 1
        return event


class TestAsyncRequestBodyReader:
    """Test cases for AsyncRequestBodyReader."""

    @pytest.mark.asyncio
    async def test_single_event_complete_body(self):
        """Test reading a complete body from a single http.request event."""
        body_data = b"Hello, ASGI world!"
        events = [{"type": "http.request", "body": body_data, "more_body": False}]

        receive = MockASGIReceive(events)
        reader = AsyncRequestBodyReader(receive)

        result = await reader.read_all()
        assert result == body_data

    @pytest.mark.asyncio
    async def test_multiple_events_partial_bodies(self):
        """Test reading body from multiple http.request events."""
        chunk1 = b"Hello, "
        chunk2 = b"ASGI "
        chunk3 = b"world!"
        expected = chunk1 + chunk2 + chunk3

        events = [
            {"type": "http.request", "body": chunk1, "more_body": True},
            {"type": "http.request", "body": chunk2, "more_body": True},
            {"type": "http.request", "body": chunk3, "more_body": False},
        ]

        receive = MockASGIReceive(events)
        reader = AsyncRequestBodyReader(receive)

        result = await reader.read_all()
        assert result == expected

    @pytest.mark.asyncio
    async def test_empty_request_body(self):
        """Test handling empty request bodies."""
        events = [{"type": "http.request", "body": b"", "more_body": False}]

        receive = MockASGIReceive(events)
        reader = AsyncRequestBodyReader(receive)

        result = await reader.read_all()
        assert result == b""

    @pytest.mark.asyncio
    async def test_empty_chunks_with_final_data(self):
        """Test handling empty chunks followed by actual data."""
        expected = b"final data"
        events = [
            {"type": "http.request", "body": b"", "more_body": True},
            {"type": "http.request", "body": b"", "more_body": True},
            {"type": "http.request", "body": expected, "more_body": False},
        ]

        receive = MockASGIReceive(events)
        reader = AsyncRequestBodyReader(receive)

        result = await reader.read_all()
        assert result == expected

    @pytest.mark.asyncio
    async def test_large_request_body_many_events(self):
        """Test handling large request bodies split across many events."""
        # Create a 100KB body split into 1KB chunks
        chunk_size = 1024
        total_size = 100 * 1024
        chunk_data = b"A" * chunk_size

        events = []
        for i in range(total_size // chunk_size):
            is_last = i == (total_size // chunk_size - 1)
            events.append({"type": "http.request", "body": chunk_data, "more_body": not is_last})

        receive = MockASGIReceive(events)
        reader = AsyncRequestBodyReader(receive)

        result = await reader.read_all()
        assert len(result) == total_size
        assert result == b"A" * total_size

    @pytest.mark.asyncio
    async def test_read_exactly_zero_bytes(self):
        """Test reading exactly zero bytes."""
        events = [{"type": "http.request", "body": b"some data", "more_body": False}]

        receive = MockASGIReceive(events)
        reader = AsyncRequestBodyReader(receive)

        result = await reader.read_exactly(0)
        assert result == b""

    @pytest.mark.asyncio
    async def test_read_exactly_from_single_event(self):
        """Test reading exact bytes from a single event."""
        body_data = b"Hello, ASGI world!"
        events = [{"type": "http.request", "body": body_data, "more_body": False}]

        receive = MockASGIReceive(events)
        reader = AsyncRequestBodyReader(receive)

        # Read first 5 bytes
        result1 = await reader.read_exactly(5)
        assert result1 == b"Hello"

        # Read next 7 bytes
        result2 = await reader.read_exactly(7)
        assert result2 == b", ASGI "

        # Read remaining bytes
        result3 = await reader.read_exactly(6)
        assert result3 == b"world!"

    @pytest.mark.asyncio
    async def test_read_exactly_across_multiple_events(self):
        """Test reading exact bytes that span multiple events."""
        events = [
            {"type": "http.request", "body": b"Hello", "more_body": True},
            {"type": "http.request", "body": b", ASGI", "more_body": True},
            {"type": "http.request", "body": b" world!", "more_body": False},
        ]

        receive = MockASGIReceive(events)
        reader = AsyncRequestBodyReader(receive)

        # Read 8 bytes spanning first two events
        result = await reader.read_exactly(8)
        assert result == b"Hello, A"

        # Read remaining bytes
        result2 = await reader.read_exactly(10)
        assert result2 == b"SGI world!"

    @pytest.mark.asyncio
    async def test_read_exactly_insufficient_data(self):
        """Test reading more bytes than available raises EOFError."""
        events = [{"type": "http.request", "body": b"short", "more_body": False}]

        receive = MockASGIReceive(events)
        reader = AsyncRequestBodyReader(receive)

        with pytest.raises(EOFError, match="Request body ended prematurely"):
            await reader.read_exactly(10)

    @pytest.mark.asyncio
    async def test_connection_disconnect_during_reading(self):
        """Test handling client disconnect during body reading."""
        events = [
            {"type": "http.request", "body": b"partial", "more_body": True},
            {"type": "http.disconnect"},
        ]

        receive = MockASGIReceive(events)
        reader = AsyncRequestBodyReader(receive)

        with pytest.raises(
            ConnectionError, match="Client disconnected during request body reading"
        ):
            await reader.read_all()

    @pytest.mark.asyncio
    async def test_unexpected_message_type(self):
        """Test handling unexpected ASGI message types."""
        events = [
            {"type": "http.request", "body": b"partial", "more_body": True},
            {
                "type": "websocket.connect"  # Unexpected message type
            },
        ]

        receive = MockASGIReceive(events)
        reader = AsyncRequestBodyReader(receive)

        with pytest.raises(RuntimeError, match="Unexpected ASGI message type"):
            await reader.read_all()

    @pytest.mark.asyncio
    async def test_content_length_validation_success(self):
        """Test successful content-length validation."""
        body_data = b"Hello, ASGI world!"
        events = [{"type": "http.request", "body": body_data, "more_body": False}]

        receive = MockASGIReceive(events)
        reader = AsyncRequestBodyReader(receive, content_length=len(body_data))

        result = await reader.read_all()
        assert result == body_data

    @pytest.mark.asyncio
    async def test_content_length_validation_too_much_data(self):
        """Test content-length validation when too much data is sent."""
        events = [{"type": "http.request", "body": b"too much data", "more_body": False}]

        receive = MockASGIReceive(events)
        reader = AsyncRequestBodyReader(receive, content_length=5)  # Expect only 5 bytes

        with pytest.raises(ConnectError, match="Request body exceeds declared content-length"):
            await reader.read_all()

    @pytest.mark.asyncio
    async def test_content_length_validation_too_little_data(self):
        """Test content-length validation when too little data is sent."""
        events = [{"type": "http.request", "body": b"short", "more_body": False}]

        receive = MockASGIReceive(events)
        reader = AsyncRequestBodyReader(receive, content_length=10)  # Expect 10 bytes

        with pytest.raises(ConnectError, match="Request body size mismatch"):
            await reader.read_all()

    @pytest.mark.asyncio
    async def test_content_length_validation_across_chunks(self):
        """Test content-length validation across multiple chunks."""
        chunk1 = b"Hello"
        chunk2 = b" ASGI"
        expected_length = len(chunk1) + len(chunk2)

        events = [
            {"type": "http.request", "body": chunk1, "more_body": True},
            {"type": "http.request", "body": chunk2, "more_body": False},
        ]

        receive = MockASGIReceive(events)
        reader = AsyncRequestBodyReader(receive, content_length=expected_length)

        result = await reader.read_all()
        assert result == chunk1 + chunk2

    @pytest.mark.asyncio
    async def test_mixed_read_operations(self):
        """Test mixing read_exactly and read_all operations."""
        body_data = b"Hello, ASGI world! This is a longer message."
        events = [{"type": "http.request", "body": body_data, "more_body": False}]

        receive = MockASGIReceive(events)
        reader = AsyncRequestBodyReader(receive)

        # Read first 5 bytes exactly
        part1 = await reader.read_exactly(5)
        assert part1 == b"Hello"

        # Read remaining bytes with read_all
        part2 = await reader.read_all()
        assert part2 == b", ASGI world! This is a longer message."

        # Verify complete data
        assert part1 + part2 == body_data


class MockASGISend:
    """Mock ASGI send callable for testing."""

    def __init__(self, should_fail: bool = False):
        """
        Initialize with optional failure mode.

        Args:
            should_fail: Whether send operations should raise exceptions
        """
        self.events: list[dict[str, Any]] = []
        self.should_fail = should_fail

    async def __call__(self, event: dict[str, Any]) -> None:
        """Record the sent event or raise if configured to fail."""
        if self.should_fail:
            raise RuntimeError("Mock send failure")
        self.events.append(event)


class TestAsyncResponseSender:
    """Test cases for AsyncResponseSender."""

    @pytest.mark.asyncio
    async def test_simple_response_start_and_body(self):
        """Test sending a simple response with start and single body."""
        send = MockASGISend()
        sender = AsyncResponseSender(send)

        # Send start
        await sender.send_start(200, [(b"content-type", b"text/plain")])

        # Send body
        await sender.send_body(b"Hello, world!", more_body=False)

        assert len(send.events) == 2

        # Check start event
        start_event = send.events[0]
        assert start_event["type"] == "http.response.start"
        assert start_event["status"] == 200
        assert start_event["headers"] == [(b"content-type", b"text/plain")]
        assert start_event["trailers"] is False

        # Check body event
        body_event = send.events[1]
        assert body_event["type"] == "http.response.body"
        assert body_event["body"] == b"Hello, world!"
        assert body_event["more_body"] is False

    @pytest.mark.asyncio
    async def test_async_context_manager_basic(self):
        """Test using AsyncResponseSender as async context manager."""
        send = MockASGISend()

        async with AsyncResponseSender(send) as sender:
            await sender.send_start(200, [(b"content-type", b"text/plain")])
            await sender.send_body(b"Hello, world!")  # more_body=True by default

        # Should have automatically finished the response with final empty body
        assert len(send.events) == 3

        # Check the body events
        first_body = send.events[1]
        assert first_body["body"] == b"Hello, world!"
        assert first_body["more_body"] is True

        final_body = send.events[2]
        assert final_body["body"] == b""
        assert final_body["more_body"] is False

    @pytest.mark.asyncio
    async def test_async_context_manager_with_trailers(self):
        """Test async context manager with trailers."""
        send = MockASGISend()

        async with AsyncResponseSender(send) as sender:
            await sender.send_start(200, [], trailers=True)
            await sender.send_body(b"content")  # more_body=True by default
            # Don't manually finish - let context manager handle trailers

        # Should have sent start, content body, final body, and empty trailers
        assert len(send.events) == 4

        # Check events in order
        assert send.events[0]["type"] == "http.response.start"
        assert send.events[0]["trailers"] is True

        assert send.events[1]["type"] == "http.response.body"
        assert send.events[1]["body"] == b"content"
        assert send.events[1]["more_body"] is True

        assert send.events[2]["type"] == "http.response.body"
        assert send.events[2]["body"] == b""
        assert send.events[2]["more_body"] is False

        assert send.events[3]["type"] == "http.response.trailers"
        assert send.events[3]["headers"] == []
