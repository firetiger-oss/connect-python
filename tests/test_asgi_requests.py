"""Tests for ASGI request processing classes."""

import gzip
from unittest.mock import AsyncMock

import pytest
from asgiref.typing import ASGIReceiveCallable
from asgiref.typing import ASGISendCallable
from asgiref.typing import HTTPRequestEvent
from asgiref.typing import HTTPScope

from connectrpc.connect_compression import GzipCodec
from connectrpc.connect_compression import IdentityCodec
from connectrpc.connect_serialization import CONNECT_JSON_SERIALIZATION
from connectrpc.connect_serialization import CONNECT_PROTOBUF_SERIALIZATION
from connectrpc.errors import BareHTTPError
from connectrpc.errors import ConnectError
from connectrpc.errors import ConnectErrorCode
from connectrpc.server_asgi_io import ASGIScope
from connectrpc.server_asgi_requests import AsyncConnectStreamingRequest
from connectrpc.server_asgi_requests import AsyncConnectUnaryRequest


class TestAsyncConnectUnaryRequest:
    """Test suite for AsyncConnectUnaryRequest class."""

    def create_http_scope(
        self,
        method: str = "POST",
        path: str = "/test.Service/Method",
        headers: list[list[bytes]] | None = None,
        content_type: str = "application/json",
        content_length: int | None = None,
    ) -> HTTPScope:
        """Create a test HTTP scope."""
        if headers is None:
            headers = [[b"content-type", content_type.encode()]]

        # Add content-length header if specified
        if content_length is not None:
            headers.append([b"content-length", str(content_length).encode()])

        return {
            "type": "http",
            "method": method,
            "path": path,
            "headers": headers,
            "query_string": b"",
            "root_path": "",
            "scheme": "http",
            "server": ("127.0.0.1", 8000),
        }

    def create_receive_with_body(self, body: bytes) -> ASGIReceiveCallable:
        """Create a mock receive callable that returns the given body."""

        async def receive() -> HTTPRequestEvent:
            return {
                "type": "http.request",
                "body": body,
                "more_body": False,
            }

        return receive

    def create_receive_with_chunked_body(self, chunks: list[bytes]) -> ASGIReceiveCallable:
        """Create a mock receive callable that returns body in chunks."""
        call_count = 0

        async def receive() -> HTTPRequestEvent:
            nonlocal call_count
            if call_count < len(chunks):
                body = chunks[call_count]
                more_body = call_count < len(chunks) - 1
                call_count += 1
                return {
                    "type": "http.request",
                    "body": body,
                    "more_body": more_body,
                }
            else:
                # Should not be called after final chunk
                raise RuntimeError("receive() called after body finished")

        return receive

    @pytest.fixture
    def mock_send(self) -> ASGISendCallable:
        """Create a mock send callable."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_from_asgi_valid_json_request(self, mock_send: ASGISendCallable):
        """Test creating AsyncConnectUnaryRequest from valid JSON request."""
        scope = self.create_http_scope(content_type="application/json")
        receive = self.create_receive_with_body(b'{"test": "data"}')

        request = await AsyncConnectUnaryRequest.from_asgi(scope, receive, mock_send)

        assert request is not None
        assert request.serialization == CONNECT_JSON_SERIALIZATION
        assert request.compression == IdentityCodec
        assert request.method == "POST"
        assert request.path == "/test.Service/Method"
        assert request.content_type == "application/json"

    @pytest.mark.asyncio
    async def test_from_asgi_valid_protobuf_request(self, mock_send: ASGISendCallable):
        """Test creating AsyncConnectUnaryRequest from valid protobuf request."""
        scope = self.create_http_scope(content_type="application/proto")
        receive = self.create_receive_with_body(b"\x08\x96\x01")  # Sample protobuf data

        request = await AsyncConnectUnaryRequest.from_asgi(scope, receive, mock_send)

        assert request is not None
        assert request.serialization == CONNECT_PROTOBUF_SERIALIZATION
        assert request.compression == IdentityCodec

    @pytest.mark.asyncio
    async def test_from_asgi_compressed_request(self, mock_send: ASGISendCallable):
        """Test creating AsyncConnectUnaryRequest from compressed request."""
        headers = [
            [b"content-type", b"application/json"],
            [b"content-encoding", b"gzip"],
        ]
        scope = self.create_http_scope(headers=headers)

        # Create gzip-compressed JSON data
        json_data = b'{"test": "compressed"}'
        compressed_data = gzip.compress(json_data)
        receive = self.create_receive_with_body(compressed_data)

        request = await AsyncConnectUnaryRequest.from_asgi(scope, receive, mock_send)

        assert request is not None
        assert request.compression == GzipCodec

    @pytest.mark.asyncio
    async def test_from_asgi_invalid_content_type(self, mock_send: ASGISendCallable):
        """Test handling of invalid content type."""
        scope = self.create_http_scope(content_type="text/plain")
        receive = self.create_receive_with_body(b"plain text")

        request = await AsyncConnectUnaryRequest.from_asgi(scope, receive, mock_send)

        assert request is None
        # Verify 415 response was sent
        mock_send.assert_called()

    @pytest.mark.asyncio
    async def test_from_asgi_unsupported_compression(self, mock_send: ASGISendCallable):
        """Test handling of unsupported compression."""
        headers = [
            [b"content-type", b"application/json"],
            [b"content-encoding", b"unsupported"],
        ]
        scope = self.create_http_scope(headers=headers)
        receive = self.create_receive_with_body(b'{"test": "data"}')

        request = await AsyncConnectUnaryRequest.from_asgi(scope, receive, mock_send)

        assert request is None
        # Verify error response was sent
        mock_send.assert_called()

    @pytest.mark.asyncio
    async def test_from_asgi_invalid_protocol_version(self, mock_send: ASGISendCallable):
        """Test handling of invalid connect-protocol-version header."""
        headers = [
            [b"content-type", b"application/json"],
            [b"connect-protocol-version", b"2"],
        ]
        scope = self.create_http_scope(headers=headers)
        receive = self.create_receive_with_body(b'{"test": "data"}')

        request = await AsyncConnectUnaryRequest.from_asgi(scope, receive, mock_send)

        assert request is None
        # Verify error response was sent
        mock_send.assert_called()

    @pytest.mark.asyncio
    async def test_from_asgi_invalid_timeout(self, mock_send: ASGISendCallable):
        """Test handling of invalid connect-timeout-ms header."""
        headers = [
            [b"content-type", b"application/json"],
            [b"connect-timeout-ms", b"not-a-number"],
        ]
        scope = self.create_http_scope(headers=headers)
        receive = self.create_receive_with_body(b'{"test": "data"}')

        request = await AsyncConnectUnaryRequest.from_asgi(scope, receive, mock_send)

        assert request is None
        # Verify error response was sent
        mock_send.assert_called()

    @pytest.mark.asyncio
    async def test_read_body_simple(self, mock_send: ASGISendCallable):
        """Test reading simple uncompressed body."""
        scope = self.create_http_scope()
        body_data = b'{"message": "hello world"}'
        receive = self.create_receive_with_body(body_data)

        request = await AsyncConnectUnaryRequest.from_asgi(scope, receive, mock_send)
        assert request is not None

        body = await request.read_body()
        assert body == body_data

    @pytest.mark.asyncio
    async def test_read_body_chunked(self, mock_send: ASGISendCallable):
        """Test reading body delivered in multiple chunks."""
        scope = self.create_http_scope()
        chunks = [b'{"mess', b'age": "hel', b'lo world"}']
        receive = self.create_receive_with_chunked_body(chunks)

        request = await AsyncConnectUnaryRequest.from_asgi(scope, receive, mock_send)
        assert request is not None

        body = await request.read_body()
        assert body == b'{"message": "hello world"}'

    @pytest.mark.asyncio
    async def test_read_body_compressed(self, mock_send: ASGISendCallable):
        """Test reading and decompressing compressed body."""
        headers = [
            [b"content-type", b"application/json"],
            [b"content-encoding", b"gzip"],
        ]
        scope = self.create_http_scope(headers=headers)

        original_data = b'{"message": "compressed hello world"}'
        compressed_data = gzip.compress(original_data)
        receive = self.create_receive_with_body(compressed_data)

        request = await AsyncConnectUnaryRequest.from_asgi(scope, receive, mock_send)
        assert request is not None

        body = await request.read_body()
        assert body == original_data

    @pytest.mark.asyncio
    async def test_read_body_cached(self, mock_send: ASGISendCallable):
        """Test that body reading is cached."""
        scope = self.create_http_scope()
        body_data = b'{"message": "cached"}'

        # Create a receive that fails if called more than once
        call_count = 0

        async def receive() -> HTTPRequestEvent:
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise RuntimeError("receive() called more than once")
            return {
                "type": "http.request",
                "body": body_data,
                "more_body": False,
            }

        request = await AsyncConnectUnaryRequest.from_asgi(scope, receive, mock_send)
        assert request is not None

        # First call should read the body
        body1 = await request.read_body()
        assert body1 == body_data

        # Second call should return cached result
        body2 = await request.read_body()
        assert body2 == body_data
        assert call_count == 1  # Verify receive was only called once

    @pytest.mark.asyncio
    async def test_read_body_empty(self, mock_send: ASGISendCallable):
        """Test reading empty body."""
        scope = self.create_http_scope()
        receive = self.create_receive_with_body(b"")

        request = await AsyncConnectUnaryRequest.from_asgi(scope, receive, mock_send)
        assert request is not None

        body = await request.read_body()
        assert body == b""

    @pytest.mark.asyncio
    async def test_read_body_malformed_compression(self, mock_send: ASGISendCallable):
        """Test handling of malformed compressed data."""
        headers = [
            [b"content-type", b"application/json"],
            [b"content-encoding", b"gzip"],
        ]
        scope = self.create_http_scope(headers=headers)

        # Invalid gzip data
        invalid_compressed_data = b"not gzip data"
        receive = self.create_receive_with_body(invalid_compressed_data)

        request = await AsyncConnectUnaryRequest.from_asgi(scope, receive, mock_send)
        assert request is not None

        with pytest.raises(ConnectError) as exc_info:
            await request.read_body()

        assert exc_info.value.code == ConnectErrorCode.INVALID_ARGUMENT
        assert "Failed to decompress gzip data" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_timeout_valid(self):
        """Test timeout validation with valid header."""
        headers = [
            [b"content-type", b"application/json"],
            [b"connect-timeout-ms", b"5000"],
        ]
        scope = ASGIScope(self.create_http_scope(headers=headers))

        timeout = AsyncConnectUnaryRequest.validate_timeout(scope)

        assert timeout.timeout_ms == 5000

    @pytest.mark.asyncio
    async def test_validate_timeout_missing(self):
        """Test timeout validation with missing header."""
        scope = ASGIScope(self.create_http_scope())

        timeout = AsyncConnectUnaryRequest.validate_timeout(scope)

        assert timeout.timeout_ms is None

    @pytest.mark.asyncio
    async def test_validate_timeout_invalid(self):
        """Test timeout validation with invalid header."""
        headers = [
            [b"content-type", b"application/json"],
            [b"connect-timeout-ms", b"not-a-number"],
        ]
        scope = ASGIScope(self.create_http_scope(headers=headers))

        with pytest.raises(ConnectError) as exc_info:
            AsyncConnectUnaryRequest.validate_timeout(scope)

        assert exc_info.value.code == ConnectErrorCode.INVALID_ARGUMENT
        assert "must be an integer" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_content_type_json(self):
        """Test content type validation for JSON."""
        scope = ASGIScope(self.create_http_scope(content_type="application/json"))

        serialization = AsyncConnectUnaryRequest.validate_content_type(scope)

        assert serialization == CONNECT_JSON_SERIALIZATION

    @pytest.mark.asyncio
    async def test_validate_content_type_protobuf(self):
        """Test content type validation for protobuf."""
        scope = ASGIScope(self.create_http_scope(content_type="application/proto"))

        serialization = AsyncConnectUnaryRequest.validate_content_type(scope)

        assert serialization == CONNECT_PROTOBUF_SERIALIZATION

    @pytest.mark.asyncio
    async def test_validate_content_type_invalid(self):
        """Test content type validation for invalid type."""
        scope = ASGIScope(self.create_http_scope(content_type="text/plain"))

        with pytest.raises(BareHTTPError) as exc_info:
            AsyncConnectUnaryRequest.validate_content_type(scope)

        assert "415 Unsupported Media Type" in exc_info.value.status_line
        assert "Accept-Post" in exc_info.value.headers

    @pytest.mark.asyncio
    async def test_validate_compression_identity(self):
        """Test compression validation for identity (no compression)."""
        scope = ASGIScope(self.create_http_scope())

        compression = AsyncConnectUnaryRequest.validate_compression(scope)

        assert compression == IdentityCodec

    @pytest.mark.asyncio
    async def test_validate_compression_gzip(self):
        """Test compression validation for gzip."""
        headers = [
            [b"content-type", b"application/json"],
            [b"content-encoding", b"gzip"],
        ]
        scope = ASGIScope(self.create_http_scope(headers=headers))

        compression = AsyncConnectUnaryRequest.validate_compression(scope)

        assert compression == GzipCodec

    @pytest.mark.asyncio
    async def test_validate_compression_unsupported(self):
        """Test compression validation for unsupported encoding."""
        headers = [
            [b"content-type", b"application/json"],
            [b"content-encoding", b"unsupported"],
        ]
        scope = ASGIScope(self.create_http_scope(headers=headers))

        with pytest.raises(ConnectError) as exc_info:
            AsyncConnectUnaryRequest.validate_compression(scope)

        assert exc_info.value.code == ConnectErrorCode.UNIMPLEMENTED
        assert "is not supported" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_connect_protocol_version_missing(self):
        """Test protocol version validation when header is missing."""
        scope = ASGIScope(self.create_http_scope())

        # Should not raise an exception (per conformance test compatibility)
        AsyncConnectUnaryRequest.validate_connect_protocol_header(scope)

    @pytest.mark.asyncio
    async def test_connect_protocol_version_valid(self):
        """Test protocol version validation with valid version."""
        headers = [
            [b"content-type", b"application/json"],
            [b"connect-protocol-version", b"1"],
        ]
        scope = ASGIScope(self.create_http_scope(headers=headers))

        # Should not raise an exception
        AsyncConnectUnaryRequest.validate_connect_protocol_header(scope)

    @pytest.mark.asyncio
    async def test_connect_protocol_version_invalid(self):
        """Test protocol version validation with invalid version."""
        headers = [
            [b"content-type", b"application/json"],
            [b"connect-protocol-version", b"2"],
        ]
        scope = ASGIScope(self.create_http_scope(headers=headers))

        with pytest.raises(ConnectError) as exc_info:
            AsyncConnectUnaryRequest.validate_connect_protocol_header(scope)

        assert exc_info.value.code == ConnectErrorCode.INVALID_ARGUMENT
        assert "unsupported connect-protocol-version" in str(exc_info.value)


class TestAsyncConnectStreamingRequest:
    """Test suite for AsyncConnectStreamingRequest class."""

    def create_http_scope(
        self,
        method: str = "POST",
        path: str = "/test.Service/StreamMethod",
        headers: list[list[bytes]] | None = None,
        content_type: str = "application/connect+json",
        content_length: int | None = None,
    ) -> HTTPScope:
        """Create a test HTTP scope for streaming requests."""
        if headers is None:
            headers = [[b"content-type", content_type.encode()]]

        # Add content-length header if specified
        if content_length is not None:
            headers.append([b"content-length", str(content_length).encode()])

        return {
            "type": "http",
            "method": method,
            "path": path,
            "headers": headers,
            "query_string": b"",
            "root_path": "",
            "scheme": "http",
            "server": ("127.0.0.1", 8000),
        }

    def create_receive_with_body(self, body: bytes) -> ASGIReceiveCallable:
        """Create a mock receive callable that returns the given body."""

        async def receive() -> HTTPRequestEvent:
            return {
                "type": "http.request",
                "body": body,
                "more_body": False,
            }

        return receive

    @pytest.fixture
    def mock_send(self) -> ASGISendCallable:
        """Create a mock send callable."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_from_asgi_valid_connect_json_request(self, mock_send: ASGISendCallable):
        """Test creating AsyncConnectStreamingRequest from valid connect+json request."""
        scope = self.create_http_scope(content_type="application/connect+json")
        receive = self.create_receive_with_body(b"envelope data")

        request = await AsyncConnectStreamingRequest.from_asgi(scope, receive, mock_send)

        assert request is not None
        assert request.serialization == CONNECT_JSON_SERIALIZATION
        assert request.compression == IdentityCodec
        assert request.method == "POST"
        assert request.path == "/test.Service/StreamMethod"
        assert request.content_type == "application/connect+json"

    @pytest.mark.asyncio
    async def test_from_asgi_valid_connect_proto_request(self, mock_send: ASGISendCallable):
        """Test creating AsyncConnectStreamingRequest from valid connect+proto request."""
        scope = self.create_http_scope(content_type="application/connect+proto")
        receive = self.create_receive_with_body(b"envelope data")

        request = await AsyncConnectStreamingRequest.from_asgi(scope, receive, mock_send)

        assert request is not None
        assert request.serialization == CONNECT_PROTOBUF_SERIALIZATION
        assert request.compression == IdentityCodec

    @pytest.mark.asyncio
    async def test_from_asgi_with_compression(self, mock_send: ASGISendCallable):
        """Test creating AsyncConnectStreamingRequest with compression."""
        headers = [
            [b"content-type", b"application/connect+json"],
            [b"connect-content-encoding", b"gzip"],
        ]
        scope = self.create_http_scope(headers=headers)
        receive = self.create_receive_with_body(b"envelope data")

        request = await AsyncConnectStreamingRequest.from_asgi(scope, receive, mock_send)

        assert request is not None
        assert request.compression == GzipCodec

    @pytest.mark.asyncio
    async def test_from_asgi_invalid_content_type_non_connect(self, mock_send: ASGISendCallable):
        """Test handling of non-connect content type."""
        scope = self.create_http_scope(content_type="application/json")
        receive = self.create_receive_with_body(b"data")

        request = await AsyncConnectStreamingRequest.from_asgi(scope, receive, mock_send)

        assert request is None
        # Verify 415 response was sent
        mock_send.assert_called()

    @pytest.mark.asyncio
    async def test_from_asgi_invalid_content_type_unknown_connect(
        self, mock_send: ASGISendCallable
    ):
        """Test handling of unknown connect content type."""
        scope = self.create_http_scope(content_type="application/connect+unknown")
        receive = self.create_receive_with_body(b"data")

        request = await AsyncConnectStreamingRequest.from_asgi(scope, receive, mock_send)

        assert request is None
        # Verify Connect error response was sent
        mock_send.assert_called()

    @pytest.mark.asyncio
    async def test_from_asgi_unsupported_compression(self, mock_send: ASGISendCallable):
        """Test handling of unsupported compression."""
        headers = [
            [b"content-type", b"application/connect+json"],
            [b"connect-content-encoding", b"unsupported"],
        ]
        scope = self.create_http_scope(headers=headers)
        receive = self.create_receive_with_body(b"data")

        request = await AsyncConnectStreamingRequest.from_asgi(scope, receive, mock_send)

        assert request is None
        # Verify error response was sent
        mock_send.assert_called()

    @pytest.mark.asyncio
    async def test_validate_content_type_connect_json(self):
        """Test content type validation for connect+json."""
        scope = ASGIScope(self.create_http_scope(content_type="application/connect+json"))

        serialization = AsyncConnectStreamingRequest.validate_content_type(scope)

        assert serialization == CONNECT_JSON_SERIALIZATION

    @pytest.mark.asyncio
    async def test_validate_content_type_connect_proto(self):
        """Test content type validation for connect+proto."""
        scope = ASGIScope(self.create_http_scope(content_type="application/connect+proto"))

        serialization = AsyncConnectStreamingRequest.validate_content_type(scope)

        assert serialization == CONNECT_PROTOBUF_SERIALIZATION

    @pytest.mark.asyncio
    async def test_validate_content_type_invalid_non_connect(self):
        """Test content type validation for non-connect type."""
        scope = ASGIScope(self.create_http_scope(content_type="application/json"))

        with pytest.raises(BareHTTPError) as exc_info:
            AsyncConnectStreamingRequest.validate_content_type(scope)

        assert "415 Unsupported Media Type" in exc_info.value.status_line
        assert "Accept-Post" in exc_info.value.headers
        assert (
            "application/connect+json, application/connect+proto"
            in exc_info.value.headers["Accept-Post"]
        )

    @pytest.mark.asyncio
    async def test_validate_content_type_invalid_unknown_connect(self):
        """Test content type validation for unknown connect type."""
        scope = ASGIScope(self.create_http_scope(content_type="application/connect+unknown"))

        with pytest.raises(ConnectError) as exc_info:
            AsyncConnectStreamingRequest.validate_content_type(scope)

        assert exc_info.value.code == ConnectErrorCode.UNIMPLEMENTED
        assert "codec not implemented" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_compression_identity(self):
        """Test compression validation for identity (no compression)."""
        scope = ASGIScope(self.create_http_scope())

        compression = AsyncConnectStreamingRequest.validate_compression(scope)

        assert compression == IdentityCodec

    @pytest.mark.asyncio
    async def test_validate_compression_gzip(self):
        """Test compression validation for gzip."""
        headers = [
            [b"content-type", b"application/connect+json"],
            [b"connect-content-encoding", b"gzip"],
        ]
        scope = ASGIScope(self.create_http_scope(headers=headers))

        compression = AsyncConnectStreamingRequest.validate_compression(scope)

        assert compression == GzipCodec

    @pytest.mark.asyncio
    async def test_validate_compression_unsupported(self):
        """Test compression validation for unsupported encoding."""
        headers = [
            [b"content-type", b"application/connect+json"],
            [b"connect-content-encoding", b"unsupported"],
        ]
        scope = ASGIScope(self.create_http_scope(headers=headers))

        with pytest.raises(ConnectError) as exc_info:
            AsyncConnectStreamingRequest.validate_compression(scope)

        assert exc_info.value.code == ConnectErrorCode.UNIMPLEMENTED
        assert "connect-content-encoding unsupported is not supported" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_response_sender_available_and_send_removed(self, mock_send: ASGISendCallable):
        """Test that streaming request has response sender and no raw send callback."""
        scope = self.create_http_scope(content_type="application/connect+json")
        receive = self.create_receive_with_body(b"envelope data")

        request = await AsyncConnectStreamingRequest.from_asgi(scope, receive, mock_send)

        assert request is not None

        # Should have response sender
        assert hasattr(request, "response")
        assert request.response is not None

        # Should NOT have raw send callback
        assert not hasattr(request, "send")

    @pytest.mark.asyncio
    async def test_send_connect_error_method(self, mock_send: ASGISendCallable):
        """Test the instance method for sending connect errors."""
        scope = self.create_http_scope(content_type="application/connect+json")
        receive = self.create_receive_with_body(b"envelope data")

        request = await AsyncConnectStreamingRequest.from_asgi(scope, receive, mock_send)

        assert request is not None

        # Should have the send_connect_error method
        assert hasattr(request, "send_connect_error")
        assert callable(request.send_connect_error)

        # Test sending an error (we won't actually send since it's complex to mock)
        # Just verify the method exists and is callable
