"""
Tests for ASGI I/O primitives in ConnectRPC server implementation.

This module tests the AsyncRequestBodyReader class that handles ASGI http.request events.
"""

from typing import Any

import pytest
from multidict import CIMultiDict

from connectrpc.errors import ConnectError
from connectrpc.server_asgi_io import ASGIResponse
from connectrpc.server_asgi_io import ASGIScope
from connectrpc.server_asgi_io import AsyncRequestBodyReader


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


class TestASGIResponse:
    """Test cases for ASGIResponse."""

    @pytest.mark.asyncio
    async def test_simple_response_start_and_body(self):
        """Test sending a simple response with start and single body."""
        send = MockASGISend()
        sender = ASGIResponse(send)

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
        """Test using ASGIResponse as async context manager."""
        send = MockASGISend()

        async with ASGIResponse(send) as sender:
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

        async with ASGIResponse(send) as sender:
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


class TestASGIScope:
    """Test cases for ASGIScope class."""

    def test_basic_http_scope(self):
        """Test basic HTTP scope parsing."""
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/eliza.v1.ElizaService/Say",
            "query_string": b"foo=bar&baz=qux",
            "headers": [
                [b"content-type", b"application/json"],
                [b"content-length", b"123"],
                [b"host", b"example.com"],
            ],
        }

        asgi_scope = ASGIScope(scope)

        assert asgi_scope.method == "POST"
        assert asgi_scope.path == "/eliza.v1.ElizaService/Say"
        assert asgi_scope.query_string == b"foo=bar&baz=qux"
        assert asgi_scope.content_type == "application/json"
        assert asgi_scope.content_length == 123
        assert asgi_scope.http_version == "1.1"  # default
        assert asgi_scope.scheme == "http"  # default
        assert asgi_scope.root_path == ""  # default

    def test_http_scope_with_all_fields(self):
        """Test HTTP scope with all optional fields."""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test/path",
            "query_string": b"param=value",
            "http_version": "2",
            "scheme": "https",
            "root_path": "/api/v1",
            "headers": [
                [b"accept", b"application/proto"],
                [b"authorization", b"Bearer token123"],
            ],
            "server": ["localhost", 8080],
            "client": ["192.168.1.100", 54321],
        }

        asgi_scope = ASGIScope(scope)

        assert asgi_scope.method == "GET"
        assert asgi_scope.path == "/test/path"
        assert asgi_scope.query_string == b"param=value"
        assert asgi_scope.http_version == "2"
        assert asgi_scope.scheme == "https"
        assert asgi_scope.root_path == "/api/v1"
        assert asgi_scope.get_server() == ("localhost", 8080)
        assert asgi_scope.get_client() == ("192.168.1.100", 54321)

    def test_header_normalization(self):
        """Test header normalization and case-insensitive access."""
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/test",
            "headers": [
                [b"Content-Type", b"application/json"],  # Mixed case
                [b"CONTENT-LENGTH", b"456"],  # Upper case
                [b"x-custom-header", b"value1"],
                [b"X-Custom-Header", b"value2"],  # Duplicate with different case
                [b"accept-encoding", b"gzip, deflate"],
            ],
        }

        asgi_scope = ASGIScope(scope)

        # Content-Type should be normalized to lowercase
        assert asgi_scope.content_type == "application/json"
        assert asgi_scope.content_length == 456

        # Headers should be accessible case-insensitively
        assert asgi_scope.get_header("content-type") == "application/json"
        assert asgi_scope.get_header("Content-Type") == "application/json"
        assert asgi_scope.get_header("CONTENT-TYPE") == "application/json"

        # Multiple headers with same name should be preserved
        custom_headers = asgi_scope.get_headers("x-custom-header")
        assert len(custom_headers) == 2
        assert "value1" in custom_headers
        assert "value2" in custom_headers

    def test_missing_headers(self):
        """Test behavior with missing headers."""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [],  # No headers
        }

        asgi_scope = ASGIScope(scope)

        assert asgi_scope.content_type == ""
        assert asgi_scope.content_length == 0
        assert asgi_scope.get_header("missing-header") is None
        assert asgi_scope.get_header("missing-header", "default") == "default"
        assert asgi_scope.get_headers("missing-header") == []

    def test_invalid_content_length(self):
        """Test handling of invalid Content-Length values."""
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/test",
            "headers": [
                [b"content-length", b"not-a-number"],
            ],
        }

        asgi_scope = ASGIScope(scope)

        # Invalid content-length should default to 0
        assert asgi_scope.content_length == 0

    def test_empty_content_length(self):
        """Test handling of empty Content-Length header."""
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/test",
            "headers": [
                [b"content-length", b""],
            ],
        }

        asgi_scope = ASGIScope(scope)

        # Empty content-length should default to 0
        assert asgi_scope.content_length == 0

    def test_header_encoding_errors(self):
        """Test handling of headers with encoding issues."""
        # Create bytes that aren't valid latin-1
        invalid_bytes = b"\x80\x81\x82"

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [
                [b"valid-header", b"valid-value"],
                [invalid_bytes, b"invalid-header-name"],  # Invalid header name
                [b"invalid-header-value", invalid_bytes],  # Invalid header value
                [b"another-valid", b"another-value"],
            ],
        }

        asgi_scope = ASGIScope(scope)

        # Valid headers should still work
        assert asgi_scope.get_header("valid-header") == "valid-value"
        assert asgi_scope.get_header("another-valid") == "another-value"

        # Invalid headers should be skipped
        assert len(asgi_scope.headers) == 2

    def test_wsgi_compatibility_interface(self):
        """Test compatibility with WSGIRequest interface expectations."""
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/eliza.v1.ElizaService/Say",
            "headers": [
                [b"content-type", b"application/proto"],
                [b"content-length", b"789"],
                [b"connect-protocol-version", b"1"],
                [b"connect-timeout-ms", b"30000"],
            ],
        }

        asgi_scope = ASGIScope(scope)

        # Should provide same interface as WSGIRequest
        assert hasattr(asgi_scope, "method")
        assert hasattr(asgi_scope, "path")
        assert hasattr(asgi_scope, "headers")
        assert hasattr(asgi_scope, "content_type")
        assert hasattr(asgi_scope, "content_length")

        # Headers should be CIMultiDict like WSGIRequest
        assert isinstance(asgi_scope.headers, CIMultiDict)

        # Connect protocol headers should be accessible
        assert asgi_scope.get_header("connect-protocol-version") == "1"
        assert asgi_scope.get_header("connect-timeout-ms") == "30000"

    def test_non_http_scope_rejection(self):
        """Test rejection of non-HTTP scopes."""
        websocket_scope = {
            "type": "websocket",
            "path": "/ws",
        }

        with pytest.raises(ValueError, match="Expected HTTP scope, got websocket"):
            ASGIScope(websocket_scope)

    def test_scope_defaults(self):
        """Test default values for missing scope fields."""
        minimal_scope = {
            "type": "http",
        }

        asgi_scope = ASGIScope(minimal_scope)

        assert asgi_scope.method == "GET"  # Default method
        assert asgi_scope.path == "/"  # Default path
        assert asgi_scope.query_string == b""  # Default query string
        assert asgi_scope.http_version == "1.1"  # Default HTTP version
        assert asgi_scope.scheme == "http"  # Default scheme
        assert asgi_scope.root_path == ""  # Default root path
        assert asgi_scope.content_type == ""  # No content-type header
        assert asgi_scope.content_length == 0  # No content-length header
        assert asgi_scope.get_server() is None  # No server info
        assert asgi_scope.get_client() is None  # No client info

    def test_repr_string(self):
        """Test string representation for debugging."""
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/test/path",
            "headers": [
                [b"content-type", b"application/json"],
            ],
        }

        asgi_scope = ASGIScope(scope)
        repr_str = repr(asgi_scope)

        assert "ASGIScope" in repr_str
        assert "POST" in repr_str
        assert "/test/path" in repr_str
        assert "application/json" in repr_str

    def test_case_insensitive_header_access(self):
        """Test comprehensive case-insensitive header access."""
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/test",
            "headers": [
                [b"content-type", b"application/json"],
                [b"X-Forwarded-For", b"192.168.1.1"],
                [b"USER-AGENT", b"TestClient/1.0"],
            ],
        }

        asgi_scope = ASGIScope(scope)

        # Test various case combinations
        assert asgi_scope.get_header("content-type") == "application/json"
        assert asgi_scope.get_header("Content-Type") == "application/json"
        assert asgi_scope.get_header("CONTENT-TYPE") == "application/json"

        assert asgi_scope.get_header("x-forwarded-for") == "192.168.1.1"
        assert asgi_scope.get_header("X-FORWARDED-FOR") == "192.168.1.1"
        assert asgi_scope.get_header("X-Forwarded-For") == "192.168.1.1"

        assert asgi_scope.get_header("user-agent") == "TestClient/1.0"
        assert asgi_scope.get_header("User-Agent") == "TestClient/1.0"
        assert asgi_scope.get_header("USER-AGENT") == "TestClient/1.0"

    @pytest.mark.asyncio
    async def test_integration_asgi_io_primitives_with_uvicorn(self):
        """Integration test: All ASGI I/O primitives working together with real uvicorn server."""
        import asyncio
        import threading
        import urllib.request

        import uvicorn

        # Storage for testing the primitives
        test_results = {
            "scope_data": None,
            "request_body": None,
            "response_sent": False,
            "error": None,
        }

        async def test_app(scope, receive, send):
            """ASGI app that tests all three I/O primitives together."""
            # Handle lifespan events (uvicorn sends these)
            if scope["type"] == "lifespan":
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                return

            # Only process HTTP requests
            if scope["type"] != "http":
                return

            try:
                # Test 1: ASGIScope extracts metadata correctly
                asgi_scope = ASGIScope(scope)
                test_results["scope_data"] = {
                    "method": asgi_scope.method,
                    "path": asgi_scope.path,
                    "content_type": asgi_scope.content_type,
                    "content_length": asgi_scope.content_length,
                    "headers": dict(asgi_scope.headers),
                }

                # Test 2: AsyncRequestBodyReader reads the body
                body_reader = AsyncRequestBodyReader(receive, asgi_scope.content_length)
                request_body = await body_reader.read_all()
                test_results["request_body"] = request_body

                # Test 3: ASGIResponse sends the response
                response_sender = ASGIResponse(send)

                # Send response headers
                await response_sender.send_start(
                    200,
                    [
                        (b"content-type", b"application/json"),
                        (b"x-test-header", b"asgi-integration"),
                    ],
                )

                # Send response body
                response_data = (
                    b'{"received_body_length": ' + str(len(request_body)).encode() + b"}"
                )
                await response_sender.send_body(response_data, more_body=False)

                test_results["response_sent"] = True

            except Exception as e:
                test_results["error"] = str(e)
                # Send error response
                await send(
                    {
                        "type": "http.response.start",
                        "status": 500,
                        "headers": [[b"content-type", b"text/plain"]],
                    }
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": f"Error: {e}".encode(),
                        "more_body": False,
                    }
                )

        # Start uvicorn server
        server_ready = threading.Event()
        server_error = None

        def run_server():
            try:
                config = uvicorn.Config(test_app, host="127.0.0.1", port=8766, log_level="error")
                server = uvicorn.Server(config)
                server_ready.set()
                asyncio.run(server.serve())
            except Exception as e:
                nonlocal server_error
                server_error = e
                server_ready.set()

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()

        # Wait for server to be ready
        server_ready.wait(timeout=5.0)
        if server_error:
            pytest.fail(f"Server failed to start: {server_error}")

        await asyncio.sleep(0.1)  # Give server time to fully start

        try:
            # Make request to test all primitives
            url = "http://127.0.0.1:8766/test/endpoint?param=value"
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "asgi-test/1.0",
                "X-Custom-Header": "test-value",
            }
            request_data = b'{"test": "data", "number": 42}'

            req = urllib.request.Request(url, data=request_data, headers=headers, method="POST")

            with urllib.request.urlopen(req, timeout=3.0) as response:
                response_body = response.read()
                response_headers = dict(response.headers)

                # Verify response
                assert response.status == 200
                assert response_headers.get("content-type") == "application/json"
                assert response_headers.get("x-test-header") == "asgi-integration"

            await asyncio.sleep(0.1)  # Give async processing time to complete

            # Verify no errors occurred
            assert test_results["error"] is None, f"ASGI app error: {test_results['error']}"

            # Test 1: Verify ASGIScope extracted metadata correctly
            scope_data = test_results["scope_data"]
            assert scope_data is not None
            assert scope_data["method"] == "POST"
            assert scope_data["path"] == "/test/endpoint"
            assert scope_data["content_type"] == "application/json"
            assert scope_data["content_length"] == len(request_data)
            assert scope_data["headers"]["user-agent"] == "asgi-test/1.0"
            assert scope_data["headers"]["x-custom-header"] == "test-value"

            # Test 2: Verify AsyncRequestBodyReader read the body correctly
            received_body = test_results["request_body"]
            assert received_body is not None
            assert received_body == request_data

            # Test 3: Verify ASGIResponse sent response correctly
            assert test_results["response_sent"] is True
            assert b'"received_body_length": 30' in response_body  # len(request_data) = 30

        except Exception as e:
            pytest.fail(f"Integration test failed: {e}")
