"""Tests for ConnectASGI server implementation."""

import asyncio
import json
import logging
import struct
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest
from asgiref.typing import ASGIReceiveCallable
from asgiref.typing import ASGISendCallable
from asgiref.typing import HTTPRequestEvent
from asgiref.typing import HTTPScope
from asgiref.typing import WebSocketScope

from connectrpc.errors import ConnectError
from connectrpc.errors import ConnectErrorCode
from connectrpc.server import ClientRequest
from connectrpc.server import ServerResponse
from connectrpc.server_asgi import ConnectASGI
from connectrpc.server_asgi_streams import AsyncClientStream
from connectrpc.server_rpc_types import RPCType
from tests.testing.testing_service_pb2 import EchoRequest
from tests.testing.testing_service_pb2 import EchoResponse


class TestConnectASGI:
    """Test suite for ConnectASGI server class."""

    def create_http_scope(
        self,
        method: str = "POST",
        path: str = "/test.Service/Method",
        headers: list[list[bytes]] | None = None,
        content_type: str = "application/json",
    ) -> HTTPScope:
        """Create a test HTTP scope."""
        if headers is None:
            headers = [[b"content-type", content_type.encode()]]

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

    def create_websocket_scope(self, path: str = "/ws") -> WebSocketScope:
        """Create a test WebSocket scope."""
        return {
            "type": "websocket",
            "path": path,
            "headers": [],
            "query_string": b"",
            "root_path": "",
            "scheme": "ws",
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
        """Create a mock send callable that records calls."""
        return AsyncMock()

    @pytest.fixture
    def app(self) -> ConnectASGI:
        """Create a test ConnectASGI server."""
        return ConnectASGI()

    def test_init(self, app: ConnectASGI):
        """Test ConnectASGI initialization."""
        assert isinstance(app.rpc_types, dict)
        assert isinstance(app.unary_rpcs, dict)
        assert isinstance(app.server_streaming_rpcs, dict)
        assert isinstance(app.client_streaming_rpcs, dict)
        assert isinstance(app.rpc_input_types, dict)
        assert len(app.rpc_types) == 0
        assert len(app.unary_rpcs) == 0
        assert len(app.server_streaming_rpcs) == 0
        assert len(app.client_streaming_rpcs) == 0
        assert len(app.rpc_input_types) == 0

    def test_register_unary_rpc(self, app: ConnectASGI):
        """Test registering a unary RPC."""

        async def test_handler(req: ClientRequest[EchoRequest]) -> ServerResponse[EchoResponse]:
            response = EchoResponse()
            response.message = "response"
            return ServerResponse(response)

        path = "/testing.TestingService/Echo"
        app.register_unary_rpc(path, test_handler, EchoRequest)

        assert app.rpc_types[path] == RPCType.UNARY
        assert app.unary_rpcs[path] == test_handler
        assert app.rpc_input_types[path] == EchoRequest

    def test_register_server_streaming_rpc(self, app: ConnectASGI):
        """Test registering a server streaming RPC."""

        async def test_handler(req: ClientRequest[EchoRequest]) -> AsyncIterator[EchoResponse]:
            for i in range(3):
                response = EchoResponse()
                response.message = f"response-{i}"
                yield response

        path = "/testing.TestingService/EchoStream"
        app.register_server_streaming_rpc(path, test_handler, EchoRequest)

        assert app.rpc_types[path] == RPCType.SERVER_STREAMING
        assert app.server_streaming_rpcs[path] == test_handler
        assert app.rpc_input_types[path] == EchoRequest

    def test_register_client_streaming_rpc(self, app: ConnectASGI):
        """Test registering a client streaming RPC."""

        async def test_handler(req: AsyncClientStream[EchoRequest]) -> ServerResponse[EchoResponse]:
            message_count = 0
            last_message = ""
            async for message in req:
                message_count += 1
                last_message = message.message

            response = EchoResponse()
            response.message = f"received {message_count} messages, last: {last_message}"
            return ServerResponse(response)

        path = "/testing.TestingService/EchoClientStream"
        app.register_client_streaming_rpc(path, test_handler, EchoRequest)

        assert app.rpc_types[path] == RPCType.CLIENT_STREAMING
        assert app.client_streaming_rpcs[path] == test_handler
        assert app.rpc_input_types[path] == EchoRequest

    @pytest.mark.asyncio
    async def test_websocket_rejection(self, app: ConnectASGI, mock_send: ASGISendCallable):
        """Test that WebSocket connections are rejected."""
        scope = self.create_websocket_scope()
        receive = AsyncMock()

        await app(scope, receive, mock_send)

        # Should send websocket.close event
        mock_send.assert_called_once_with({"type": "websocket.close", "code": 1002, "reason": ""})

    @pytest.mark.asyncio
    async def test_unknown_scope_type(self, app: ConnectASGI, mock_send: ASGISendCallable):
        """Test handling of unknown ASGI scope types."""
        scope = {"type": "unknown"}  # type: ignore[typeddict-item]
        receive = AsyncMock()

        # Should not crash when handling unknown scope types
        await app(scope, receive, mock_send)

        # Should not send any response (can't send HTTP response for non-HTTP scope)
        mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_method_not_allowed(self, app: ConnectASGI, mock_send: ASGISendCallable):
        """Test handling of non-POST HTTP methods."""
        scope = self.create_http_scope(method="GET")
        receive = AsyncMock()

        await app(scope, receive, mock_send)

        # Should send 405 Method Not Allowed with Allow header
        calls = mock_send.call_args_list
        assert len(calls) == 2

        start_call = calls[0]
        assert start_call[0][0]["type"] == "http.response.start"
        assert start_call[0][0]["status"] == 405

        # Check for Allow header
        headers = start_call[0][0]["headers"]
        allow_header = next((h for h in headers if h[0] == b"allow"), None)
        assert allow_header is not None
        assert allow_header[1] == b"POST"

    @pytest.mark.asyncio
    async def test_not_found(self, app: ConnectASGI, mock_send: ASGISendCallable):
        """Test handling of unknown RPC paths."""
        scope = self.create_http_scope(path="/unknown/path")
        receive = AsyncMock()

        await app(scope, receive, mock_send)

        # Should send 404 Not Found
        calls = mock_send.call_args_list
        assert len(calls) == 2

        start_call = calls[0]
        assert start_call[0][0]["type"] == "http.response.start"
        assert start_call[0][0]["status"] == 404

    @pytest.mark.asyncio
    async def test_bidi_streaming_not_implemented(
        self, app: ConnectASGI, mock_send: ASGISendCallable
    ):
        """Test that bidirectional streaming RPCs return 501 Not Implemented."""
        # Test bidirectional streaming not implemented
        path = "/test.Service/BidiStreamingMethod"
        app.rpc_types[path] = RPCType.BIDI_STREAMING

        scope = self.create_http_scope(path=path)
        receive = AsyncMock()

        await app(scope, receive, mock_send)

        # Should send 501 Not Implemented
        calls = mock_send.call_args_list
        assert len(calls) == 2

        start_call = calls[0]
        assert start_call[0][0]["type"] == "http.response.start"
        assert start_call[0][0]["status"] == 501

    @pytest.mark.asyncio
    async def test_successful_unary_rpc(self, app: ConnectASGI, mock_send: ASGISendCallable):
        """Test successful unary RPC execution."""

        # Register a test handler
        async def test_handler(req: ClientRequest[EchoRequest]) -> ServerResponse[EchoResponse]:
            response = EchoResponse()
            response.message = f"echo: {req.msg.message}"
            return ServerResponse(response)

        path = "/testing.TestingService/Echo"
        app.register_unary_rpc(path, test_handler, EchoRequest)

        # Create request
        request_body = json.dumps({"message": "hello"}).encode()
        scope = self.create_http_scope(path=path)
        receive = self.create_receive_with_body(request_body)

        await app(scope, receive, mock_send)

        # Check response
        calls = mock_send.call_args_list
        assert len(calls) == 2

        start_call = calls[0]
        assert start_call[0][0]["type"] == "http.response.start"
        assert start_call[0][0]["status"] == 200

        # Check content-type header
        headers = start_call[0][0]["headers"]
        content_type_header = next((h for h in headers if h[0] == b"content-type"), None)
        assert content_type_header is not None
        assert content_type_header[1] == b"application/json"

        body_call = calls[1]
        assert body_call[0][0]["type"] == "http.response.body"
        assert not body_call[0][0]["more_body"]

        # Parse response body
        response_data = body_call[0][0]["body"]
        response_json = json.loads(response_data.decode())
        assert response_json["message"] == "echo: hello"

    @pytest.mark.asyncio
    async def test_unary_rpc_with_connect_error(
        self, app: ConnectASGI, mock_send: ASGISendCallable
    ):
        """Test unary RPC that returns a ConnectError."""

        # Register a handler that returns an error
        async def error_handler(req: ClientRequest[EchoRequest]) -> ServerResponse[EchoResponse]:
            error = ConnectError(ConnectErrorCode.INVALID_ARGUMENT, "Test error")
            return ServerResponse(error)

        path = "/testing.TestingService/Echo"
        app.register_unary_rpc(path, error_handler, EchoRequest)

        # Create request
        request_body = json.dumps({"message": "test"}).encode()
        scope = self.create_http_scope(path=path)
        receive = self.create_receive_with_body(request_body)

        await app(scope, receive, mock_send)

        # Check error response
        calls = mock_send.call_args_list
        assert len(calls) == 2

        start_call = calls[0]
        assert start_call[0][0]["type"] == "http.response.start"
        assert start_call[0][0]["status"] == 400  # INVALID_ARGUMENT maps to 400

        body_call = calls[1]
        response_data = body_call[0][0]["body"]
        error_json = json.loads(response_data.decode())
        assert error_json["code"] == "invalid_argument"
        assert error_json["message"] == "Test error"

    @pytest.mark.asyncio
    async def test_unary_rpc_handler_exception(self, app: ConnectASGI, mock_send: ASGISendCallable):
        """Test unary RPC where handler raises an exception."""

        # Register a handler that raises an exception
        async def exception_handler(
            req: ClientRequest[EchoRequest],
        ) -> ServerResponse[EchoResponse]:
            raise ValueError("Handler exception")

        path = "/testing.TestingService/Echo"
        app.register_unary_rpc(path, exception_handler, EchoRequest)

        # Create request
        request_body = json.dumps({"message": "test"}).encode()
        scope = self.create_http_scope(path=path)
        receive = self.create_receive_with_body(request_body)

        await app(scope, receive, mock_send)

        # Check internal error response
        calls = mock_send.call_args_list
        assert len(calls) == 2

        start_call = calls[0]
        assert start_call[0][0]["type"] == "http.response.start"
        assert start_call[0][0]["status"] == 500  # INTERNAL maps to 500

        body_call = calls[1]
        response_data = body_call[0][0]["body"]
        error_json = json.loads(response_data.decode())
        assert error_json["code"] == "internal"
        assert "Handler exception" in error_json["message"]

    @pytest.mark.asyncio
    async def test_invalid_request_validation(self, app: ConnectASGI, mock_send: ASGISendCallable):
        """Test handling of invalid requests during validation."""

        # Register a handler
        async def test_handler(req: ClientRequest[EchoRequest]) -> ServerResponse[EchoResponse]:
            response = EchoResponse()
            response.message = "response"
            return ServerResponse(response)

        path = "/testing.TestingService/Echo"
        app.register_unary_rpc(path, test_handler, EchoRequest)

        # Create request with invalid content-type
        scope = self.create_http_scope(path=path, content_type="text/plain")
        receive = self.create_receive_with_body(b"invalid data")

        await app(scope, receive, mock_send)

        # Should get validation error (415 Unsupported Media Type)
        calls = mock_send.call_args_list
        assert len(calls) == 2

        start_call = calls[0]
        assert start_call[0][0]["type"] == "http.response.start"
        assert start_call[0][0]["status"] == 415

    @pytest.mark.asyncio
    async def test_response_headers_and_trailers(
        self, app: ConnectASGI, mock_send: ASGISendCallable
    ):
        """Test that response headers and trailers are properly sent."""
        from multidict import CIMultiDict

        # Register a handler that sets headers and trailers
        async def header_handler(req: ClientRequest[EchoRequest]) -> ServerResponse[EchoResponse]:
            headers = CIMultiDict([("X-Custom-Header", "custom-value")])
            trailers = CIMultiDict([("X-Custom-Trailer", "trailer-value")])
            response = EchoResponse()
            response.message = "response"
            return ServerResponse(response, headers=headers, trailers=trailers)

        path = "/testing.TestingService/Echo"
        app.register_unary_rpc(path, header_handler, EchoRequest)

        # Create request
        request_body = json.dumps({"message": "test"}).encode()
        scope = self.create_http_scope(path=path)
        receive = self.create_receive_with_body(request_body)

        await app(scope, receive, mock_send)

        # Check response headers
        calls = mock_send.call_args_list
        assert len(calls) == 2

        start_call = calls[0]
        headers = start_call[0][0]["headers"]

        # Check for custom header
        custom_header = next((h for h in headers if h[0] == b"x-custom-header"), None)
        assert custom_header is not None
        assert custom_header[1] == b"custom-value"

        # Check for trailer header (prefixed with "trailer-")
        trailer_header = next((h for h in headers if h[0] == b"trailer-x-custom-trailer"), None)
        assert trailer_header is not None
        assert trailer_header[1] == b"trailer-value"


class TestConnectASGIServerStreaming:
    """Test suite for ConnectASGI server streaming functionality."""

    def create_http_scope(
        self,
        method: str = "POST",
        path: str = "/test.Service/Method",
        headers: list[list[bytes]] | None = None,
        content_type: str = "application/json",
    ) -> HTTPScope:
        """Create a test HTTP scope."""
        if headers is None:
            headers = [[b"content-type", content_type.encode()]]

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
        """Create a mock send callable that records calls."""
        return AsyncMock()

    @pytest.fixture
    def app(self) -> ConnectASGI:
        """Create a test ConnectASGI server."""
        return ConnectASGI()

    @pytest.mark.asyncio
    async def test_successful_server_streaming_empty_stream(
        self, app: ConnectASGI, mock_send: ASGISendCallable
    ):
        """Test server streaming RPC that returns empty stream."""

        async def empty_stream_handler(
            req: ClientRequest[EchoRequest],
        ) -> AsyncIterator[EchoResponse]:
            return
            yield  # unreachable, but makes this an async generator

        path = "/testing.TestingService/EchoStream"
        app.register_server_streaming_rpc(path, empty_stream_handler, EchoRequest)

        # Create request using Connect envelope format (server streaming uses streaming request format)
        from connectrpc.connect_serialization import CONNECT_JSON_SERIALIZATION

        test_msg = EchoRequest(message="test")
        serialized_data = CONNECT_JSON_SERIALIZATION.serialize(test_msg)

        # Create Connect envelope: [1 byte flags][4 bytes big-endian length][data]
        envelope_header = struct.pack(
            ">BI", 0, len(serialized_data)
        )  # flags=0 (no compression, not end-stream)
        message_envelope = envelope_header + serialized_data

        # Create end-stream envelope
        end_stream_data = b'{"metadata":{}}'
        end_envelope_header = struct.pack(">BI", 2, len(end_stream_data))  # flags=2 (end-stream)
        end_stream_envelope = end_envelope_header + end_stream_data

        request_body = message_envelope + end_stream_envelope
        scope = self.create_http_scope(path=path, content_type="application/connect+json")
        receive = self.create_receive_with_body(request_body)

        await app(scope, receive, mock_send)

        # Check response
        calls = mock_send.call_args_list
        assert len(calls) >= 2  # start + at least end-stream

        # Check start response
        start_call = calls[0]
        assert start_call[0][0]["type"] == "http.response.start"
        assert start_call[0][0]["status"] == 200

        # Check content-type header (should be streaming JSON)
        headers = start_call[0][0]["headers"]
        content_type_header = next((h for h in headers if h[0] == b"content-type"), None)
        assert content_type_header is not None
        assert content_type_header[1] == b"application/connect+json"

    @pytest.mark.asyncio
    async def test_successful_server_streaming_single_message(
        self, app: ConnectASGI, mock_send: ASGISendCallable
    ):
        """Test server streaming RPC that returns single message."""

        async def single_message_handler(
            req: ClientRequest[EchoRequest],
        ) -> AsyncIterator[EchoResponse]:
            response = EchoResponse()
            response.message = f"echo: {req.msg.message}"
            yield response

        path = "/testing.TestingService/EchoStream"
        app.register_server_streaming_rpc(path, single_message_handler, EchoRequest)

        # Create request using Connect envelope format (server streaming uses streaming request format)
        from connectrpc.connect_serialization import CONNECT_JSON_SERIALIZATION

        test_msg = EchoRequest(message="hello")
        serialized_data = CONNECT_JSON_SERIALIZATION.serialize(test_msg)

        # Create Connect envelope: [1 byte flags][4 bytes big-endian length][data]
        envelope_header = struct.pack(
            ">BI", 0, len(serialized_data)
        )  # flags=0 (no compression, not end-stream)
        message_envelope = envelope_header + serialized_data

        # Create end-stream envelope
        end_stream_data = b'{"metadata":{}}'
        end_envelope_header = struct.pack(">BI", 2, len(end_stream_data))  # flags=2 (end-stream)
        end_stream_envelope = end_envelope_header + end_stream_data

        request_body = message_envelope + end_stream_envelope
        scope = self.create_http_scope(path=path, content_type="application/connect+json")
        receive = self.create_receive_with_body(request_body)

        await app(scope, receive, mock_send)

        # Check response
        calls = mock_send.call_args_list
        assert len(calls) >= 3  # start + message + end-stream

        # Check start response
        start_call = calls[0]
        assert start_call[0][0]["type"] == "http.response.start"
        assert start_call[0][0]["status"] == 200

        # Check that at least one body chunk was sent (message envelope)
        body_calls = [call for call in calls if call[0][0]["type"] == "http.response.body"]
        assert len(body_calls) >= 1

        # Check final call indicates end of stream
        final_call = calls[-1]
        assert final_call[0][0]["type"] == "http.response.body"
        assert final_call[0][0]["more_body"] is False

    @pytest.mark.asyncio
    async def test_successful_server_streaming_multiple_messages(
        self, app: ConnectASGI, mock_send: ASGISendCallable
    ):
        """Test server streaming RPC that returns multiple messages."""

        async def multi_message_handler(
            req: ClientRequest[EchoRequest],
        ) -> AsyncIterator[EchoResponse]:
            for i in range(3):
                response = EchoResponse()
                response.message = f"echo-{i}: {req.msg.message}"
                yield response

        path = "/testing.TestingService/EchoStream"
        app.register_server_streaming_rpc(path, multi_message_handler, EchoRequest)

        # Create request using Connect envelope format (server streaming uses streaming request format)
        from connectrpc.connect_serialization import CONNECT_JSON_SERIALIZATION

        test_msg = EchoRequest(message="hello")
        serialized_data = CONNECT_JSON_SERIALIZATION.serialize(test_msg)

        # Create Connect envelope: [1 byte flags][4 bytes big-endian length][data]
        envelope_header = struct.pack(
            ">BI", 0, len(serialized_data)
        )  # flags=0 (no compression, not end-stream)
        message_envelope = envelope_header + serialized_data

        # Create end-stream envelope
        end_stream_data = b'{"metadata":{}}'
        end_envelope_header = struct.pack(">BI", 2, len(end_stream_data))  # flags=2 (end-stream)
        end_stream_envelope = end_envelope_header + end_stream_data

        request_body = message_envelope + end_stream_envelope
        scope = self.create_http_scope(path=path, content_type="application/connect+json")
        receive = self.create_receive_with_body(request_body)

        await app(scope, receive, mock_send)

        # Check response
        calls = mock_send.call_args_list
        assert (
            len(calls) >= 4
        )  # start + 3 messages + end-stream (messages and end-stream might be combined)

        # Check start response
        start_call = calls[0]
        assert start_call[0][0]["type"] == "http.response.start"
        assert start_call[0][0]["status"] == 200

        # Check that multiple body chunks were sent
        body_calls = [call for call in calls if call[0][0]["type"] == "http.response.body"]
        assert len(body_calls) >= 1

        # Check final call indicates end of stream
        final_call = calls[-1]
        assert final_call[0][0]["type"] == "http.response.body"
        assert final_call[0][0]["more_body"] is False

    @pytest.mark.asyncio
    async def test_server_streaming_handler_exception(
        self, app: ConnectASGI, mock_send: ASGISendCallable
    ):
        """Test server streaming RPC where handler raises an exception."""

        async def failing_handler(req: ClientRequest[EchoRequest]) -> AsyncIterator[EchoResponse]:
            yield EchoResponse(message="first")
            raise ValueError("Handler exception")

        path = "/testing.TestingService/EchoStream"
        app.register_server_streaming_rpc(path, failing_handler, EchoRequest)

        # Create request using Connect envelope format (server streaming uses streaming request format)
        from connectrpc.connect_serialization import CONNECT_JSON_SERIALIZATION

        test_msg = EchoRequest(message="test")
        serialized_data = CONNECT_JSON_SERIALIZATION.serialize(test_msg)

        # Create Connect envelope: [1 byte flags][4 bytes big-endian length][data]
        envelope_header = struct.pack(
            ">BI", 0, len(serialized_data)
        )  # flags=0 (no compression, not end-stream)
        message_envelope = envelope_header + serialized_data

        # Create end-stream envelope
        end_stream_data = b'{"metadata":{}}'
        end_envelope_header = struct.pack(">BI", 2, len(end_stream_data))  # flags=2 (end-stream)
        end_stream_envelope = end_envelope_header + end_stream_data

        request_body = message_envelope + end_stream_envelope
        scope = self.create_http_scope(path=path, content_type="application/connect+json")
        receive = self.create_receive_with_body(request_body)

        await app(scope, receive, mock_send)

        # Check that we get start response followed by error handling
        calls = mock_send.call_args_list
        assert len(calls) >= 2

        # Check start response (streaming responses always start with 200)
        start_call = calls[0]
        assert start_call[0][0]["type"] == "http.response.start"
        assert start_call[0][0]["status"] == 200

    @pytest.mark.asyncio
    async def test_server_streaming_invalid_request_validation(
        self, app: ConnectASGI, mock_send: ASGISendCallable
    ):
        """Test server streaming with invalid request validation."""

        async def stream_handler(req: ClientRequest[EchoRequest]) -> AsyncIterator[EchoResponse]:
            response = EchoResponse()
            response.message = "response"
            yield response

        path = "/testing.TestingService/EchoStream"
        app.register_server_streaming_rpc(path, stream_handler, EchoRequest)

        # Create request with invalid content-type (should use application/json for unary request)
        scope = self.create_http_scope(path=path, content_type="text/plain")
        receive = self.create_receive_with_body(b"invalid data")

        await app(scope, receive, mock_send)

        # Should get validation error (415 Unsupported Media Type)
        calls = mock_send.call_args_list
        assert len(calls) == 2

        start_call = calls[0]
        assert start_call[0][0]["type"] == "http.response.start"
        assert start_call[0][0]["status"] == 415

    def _parse_envelope_from_body(self, body_data: bytes) -> tuple[int, bytes]:
        """Parse Connect envelope from body data.

        Returns tuple of (flags, data)
        """
        if len(body_data) < 5:
            return 0, b""

        flags, length = struct.unpack(">BI", body_data[:5])
        data = body_data[5 : 5 + length]
        return flags, data

    @pytest.mark.asyncio
    async def test_server_streaming_envelope_format(
        self, app: ConnectASGI, mock_send: ASGISendCallable
    ):
        """Test that server streaming responses use proper Connect envelope format."""

        async def envelope_test_handler(
            req: ClientRequest[EchoRequest],
        ) -> AsyncIterator[EchoResponse]:
            response = EchoResponse()
            response.message = "test response"
            yield response

        path = "/testing.TestingService/EchoStream"
        app.register_server_streaming_rpc(path, envelope_test_handler, EchoRequest)

        # Create request using Connect envelope format (server streaming uses streaming request format)
        from connectrpc.connect_serialization import CONNECT_JSON_SERIALIZATION

        test_msg = EchoRequest(message="test")
        serialized_data = CONNECT_JSON_SERIALIZATION.serialize(test_msg)

        # Create Connect envelope: [1 byte flags][4 bytes big-endian length][data]
        envelope_header = struct.pack(
            ">BI", 0, len(serialized_data)
        )  # flags=0 (no compression, not end-stream)
        message_envelope = envelope_header + serialized_data

        # Create end-stream envelope
        end_stream_data = b'{"metadata":{}}'
        end_envelope_header = struct.pack(">BI", 2, len(end_stream_data))  # flags=2 (end-stream)
        end_stream_envelope = end_envelope_header + end_stream_data

        request_body = message_envelope + end_stream_envelope
        scope = self.create_http_scope(path=path, content_type="application/connect+json")
        receive = self.create_receive_with_body(request_body)

        await app(scope, receive, mock_send)

        # Extract body calls
        calls = mock_send.call_args_list
        body_calls = [call for call in calls if call[0][0]["type"] == "http.response.body"]

        assert len(body_calls) >= 1

        # Check that body data follows envelope format
        for body_call in body_calls:
            body_data = body_call[0][0]["body"]
            if len(body_data) >= 5:  # Must have at least envelope header
                flags, data = self._parse_envelope_from_body(body_data)
                # flags should be 0 (normal message) or 2 (end-stream)
                assert flags in [0, 2]

                if flags == 2:  # End-stream envelope
                    # End-stream data should be valid JSON
                    try:
                        json.loads(data.decode())
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pytest.fail("End-stream envelope should contain valid JSON")


class TestConnectASGIClientStreaming:
    """Test suite for ConnectASGI client streaming functionality."""

    def create_http_scope(
        self,
        method: str = "POST",
        path: str = "/test.Service/Method",
        headers: list[list[bytes]] | None = None,
        content_type: str = "application/connect+json",
    ) -> HTTPScope:
        """Create a test HTTP scope."""
        if headers is None:
            headers = [[b"content-type", content_type.encode()]]

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

    def create_streaming_request_body(self, messages: list[EchoRequest]) -> bytes:
        """Create streaming request body with multiple messages in Connect envelope format."""
        from connectrpc.connect_serialization import CONNECT_JSON_SERIALIZATION

        request_body = b""

        # Add each message as an envelope
        for message in messages:
            serialized_data = CONNECT_JSON_SERIALIZATION.serialize(message)
            envelope_header = struct.pack(
                ">BI", 0, len(serialized_data)
            )  # flags=0 (no compression, not end-stream)
            message_envelope = envelope_header + serialized_data
            request_body += message_envelope

        # Add end-stream envelope
        end_stream_data = b'{"metadata":{}}'
        end_envelope_header = struct.pack(">BI", 2, len(end_stream_data))  # flags=2 (end-stream)
        end_stream_envelope = end_envelope_header + end_stream_data
        request_body += end_stream_envelope

        return request_body

    @pytest.fixture
    def mock_send(self) -> ASGISendCallable:
        """Create a mock send callable that records calls."""
        return AsyncMock()

    @pytest.fixture
    def app(self) -> ConnectASGI:
        """Create a test ConnectASGI server."""
        return ConnectASGI()

    @pytest.mark.asyncio
    async def test_successful_client_streaming_single_message(
        self, app: ConnectASGI, mock_send: ASGISendCallable
    ):
        """Test client streaming RPC that receives single message."""

        async def single_message_handler(
            req: AsyncClientStream[EchoRequest],
        ) -> ServerResponse[EchoResponse]:
            message_count = 0
            last_message = ""
            async for message in req:
                message_count += 1
                last_message = message.message

            response = EchoResponse()
            response.message = f"received {message_count} messages, last: {last_message}"
            return ServerResponse(response)

        path = "/testing.TestingService/EchoClientStream"
        app.register_client_streaming_rpc(path, single_message_handler, EchoRequest)

        # Create request with single message
        messages = [EchoRequest(message="hello")]
        request_body = self.create_streaming_request_body(messages)
        scope = self.create_http_scope(path=path)
        receive = self.create_receive_with_body(request_body)

        await app(scope, receive, mock_send)

        # Check response
        calls = mock_send.call_args_list
        assert len(calls) >= 2  # start + response message + end-stream

        # Check start response
        start_call = calls[0]
        assert start_call[0][0]["type"] == "http.response.start"
        assert start_call[0][0]["status"] == 200

        # Check content-type header (should be streaming JSON)
        headers = start_call[0][0]["headers"]
        content_type_header = next((h for h in headers if h[0] == b"content-type"), None)
        assert content_type_header is not None
        assert content_type_header[1] == b"application/connect+json"

    @pytest.mark.asyncio
    async def test_successful_client_streaming_multiple_messages(
        self, app: ConnectASGI, mock_send: ASGISendCallable
    ):
        """Test client streaming RPC that receives multiple messages."""

        async def multi_message_handler(
            req: AsyncClientStream[EchoRequest],
        ) -> ServerResponse[EchoResponse]:
            messages = []
            async for message in req:
                messages.append(message.message)

            response = EchoResponse()
            response.message = f"received {len(messages)} messages: {', '.join(messages)}"
            return ServerResponse(response)

        path = "/testing.TestingService/EchoClientStream"
        app.register_client_streaming_rpc(path, multi_message_handler, EchoRequest)

        # Create request with multiple messages
        messages = [
            EchoRequest(message="hello"),
            EchoRequest(message="world"),
            EchoRequest(message="test"),
        ]
        request_body = self.create_streaming_request_body(messages)
        scope = self.create_http_scope(path=path)
        receive = self.create_receive_with_body(request_body)

        await app(scope, receive, mock_send)

        # Check response
        calls = mock_send.call_args_list
        assert len(calls) >= 2  # start + response message + end-stream

        # Check start response
        start_call = calls[0]
        assert start_call[0][0]["type"] == "http.response.start"
        assert start_call[0][0]["status"] == 200

    @pytest.mark.asyncio
    async def test_successful_client_streaming_empty_stream(
        self, app: ConnectASGI, mock_send: ASGISendCallable
    ):
        """Test client streaming RPC that receives empty stream."""

        async def empty_stream_handler(
            req: AsyncClientStream[EchoRequest],
        ) -> ServerResponse[EchoResponse]:
            message_count = 0
            async for _message in req:
                message_count += 1

            response = EchoResponse()
            response.message = f"received {message_count} messages"
            return ServerResponse(response)

        path = "/testing.TestingService/EchoClientStream"
        app.register_client_streaming_rpc(path, empty_stream_handler, EchoRequest)

        # Create request with no messages (just end-stream)
        messages: list[EchoRequest] = []
        request_body = self.create_streaming_request_body(messages)
        scope = self.create_http_scope(path=path)
        receive = self.create_receive_with_body(request_body)

        await app(scope, receive, mock_send)

        # Check response
        calls = mock_send.call_args_list
        assert len(calls) >= 2  # start + response message + end-stream

        # Check start response
        start_call = calls[0]
        assert start_call[0][0]["type"] == "http.response.start"
        assert start_call[0][0]["status"] == 200

    @pytest.mark.asyncio
    async def test_client_streaming_handler_error(
        self, app: ConnectASGI, mock_send: ASGISendCallable
    ):
        """Test client streaming RPC where handler returns an error."""

        async def error_handler(
            req: AsyncClientStream[EchoRequest],
        ) -> ServerResponse[EchoResponse]:
            async for message in req:
                if message.message == "error":
                    error = ConnectError(ConnectErrorCode.INVALID_ARGUMENT, "Test error")
                    return ServerResponse(error)

            response = EchoResponse()
            response.message = "no error"
            return ServerResponse(response)

        path = "/testing.TestingService/EchoClientStream"
        app.register_client_streaming_rpc(path, error_handler, EchoRequest)

        # Create request with error-triggering message
        messages = [EchoRequest(message="error")]
        request_body = self.create_streaming_request_body(messages)
        scope = self.create_http_scope(path=path)
        receive = self.create_receive_with_body(request_body)

        await app(scope, receive, mock_send)

        # Check response
        calls = mock_send.call_args_list
        assert len(calls) >= 2  # start + end-stream with error

        # Check start response (streaming errors use HTTP 200)
        start_call = calls[0]
        assert start_call[0][0]["type"] == "http.response.start"
        assert start_call[0][0]["status"] == 200

    @pytest.mark.asyncio
    async def test_client_streaming_handler_exception(
        self, app: ConnectASGI, mock_send: ASGISendCallable
    ):
        """Test client streaming RPC where handler raises an exception."""

        async def exception_handler(
            req: AsyncClientStream[EchoRequest],
        ) -> ServerResponse[EchoResponse]:
            async for message in req:
                if message.message == "exception":
                    raise ValueError("Handler exception")

            response = EchoResponse()
            response.message = "no exception"
            return ServerResponse(response)

        path = "/testing.TestingService/EchoClientStream"
        app.register_client_streaming_rpc(path, exception_handler, EchoRequest)

        # Create request with exception-triggering message
        messages = [EchoRequest(message="exception")]
        request_body = self.create_streaming_request_body(messages)
        scope = self.create_http_scope(path=path)
        receive = self.create_receive_with_body(request_body)

        await app(scope, receive, mock_send)

        # Check response
        calls = mock_send.call_args_list
        assert len(calls) >= 2  # start + error body

        # Check start response (handler exceptions before streaming starts use HTTP 500)
        start_call = calls[0]
        assert start_call[0][0]["type"] == "http.response.start"
        assert start_call[0][0]["status"] == 500  # Internal error

    @pytest.mark.asyncio
    async def test_client_streaming_invalid_request_validation(
        self, app: ConnectASGI, mock_send: ASGISendCallable
    ):
        """Test client streaming with invalid request validation."""

        async def stream_handler(
            req: AsyncClientStream[EchoRequest],
        ) -> ServerResponse[EchoResponse]:
            response = EchoResponse()
            response.message = "response"
            return ServerResponse(response)

        path = "/testing.TestingService/EchoClientStream"
        app.register_client_streaming_rpc(path, stream_handler, EchoRequest)

        # Create request with invalid content-type (should use application/connect+json for streaming)
        scope = self.create_http_scope(path=path, content_type="text/plain")
        receive = self.create_receive_with_body(b"invalid data")

        await app(scope, receive, mock_send)

        # Should get validation error (415 Unsupported Media Type)
        calls = mock_send.call_args_list
        assert len(calls) == 2

        start_call = calls[0]
        assert start_call[0][0]["type"] == "http.response.start"
        assert start_call[0][0]["status"] == 415

    @pytest.mark.asyncio
    async def test_client_streaming_with_headers_and_trailers(
        self, app: ConnectASGI, mock_send: ASGISendCallable
    ):
        """Test client streaming RPC with custom headers and trailers."""
        from multidict import CIMultiDict

        async def header_handler(
            req: AsyncClientStream[EchoRequest],
        ) -> ServerResponse[EchoResponse]:
            message_count = 0
            async for _message in req:
                message_count += 1

            headers = CIMultiDict([("X-Custom-Header", "custom-value")])
            trailers = CIMultiDict([("X-Custom-Trailer", "trailer-value")])
            response = EchoResponse()
            response.message = f"received {message_count} messages"
            return ServerResponse(response, headers=headers, trailers=trailers)

        path = "/testing.TestingService/EchoClientStream"
        app.register_client_streaming_rpc(path, header_handler, EchoRequest)

        # Create request with single message
        messages = [EchoRequest(message="test")]
        request_body = self.create_streaming_request_body(messages)
        scope = self.create_http_scope(path=path)
        receive = self.create_receive_with_body(request_body)

        await app(scope, receive, mock_send)

        # Check response headers
        calls = mock_send.call_args_list
        assert len(calls) >= 2

        start_call = calls[0]
        headers = start_call[0][0]["headers"]

        # Check for custom header
        custom_header = next((h for h in headers if h[0] == b"x-custom-header"), None)
        assert custom_header is not None
        assert custom_header[1] == b"custom-value"


class TestConnectASGIErrorHandling:
    """Test suite for ConnectASGI error handling and resilience."""

    @pytest.fixture
    def app_with_logger(self) -> ConnectASGI:
        """Create a test ConnectASGI server with custom logger."""
        logger = logging.getLogger("test_asgi")
        logger.setLevel(logging.DEBUG)
        return ConnectASGI(logger=logger)

    def create_http_scope(
        self,
        method: str = "POST",
        path: str = "/test.Service/Method",
        headers: list[list[bytes]] | None = None,
        content_type: str = "application/json",
    ) -> HTTPScope:
        """Create a test HTTP scope."""
        if headers is None:
            headers = [[b"content-type", content_type.encode()]]

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

    def create_receive_with_disconnect(self, delay: float = 0.1) -> ASGIReceiveCallable:
        """Create a receive callable that simulates client disconnect."""

        async def receive():
            await asyncio.sleep(delay)
            return {"type": "http.disconnect"}

        return receive

    def create_receive_with_exception(self, exception: Exception) -> ASGIReceiveCallable:
        """Create a receive callable that raises an exception."""

        async def receive():
            raise exception

        return receive

    @pytest.mark.asyncio
    async def test_logging_configuration(self, app_with_logger: ConnectASGI):
        """Test that logging is properly configured."""
        # Test default logger
        app1 = ConnectASGI()
        assert app1._logger.name == "connectrpc.server_asgi"

        # Test custom logger
        custom_logger = logging.getLogger("custom")
        app2 = ConnectASGI(logger=custom_logger)
        assert app2._logger is custom_logger

    @pytest.mark.asyncio
    async def test_client_disconnect_during_body_reading(self, app_with_logger: ConnectASGI):
        """Test proper handling of client disconnects during request body reading."""

        # Register a simple handler
        async def echo_handler(req: ClientRequest[EchoRequest]) -> ServerResponse[EchoResponse]:
            response = EchoResponse()
            response.message = f"echo: {req.msg.message}"
            return ServerResponse(response)

        path = "/testing.TestingService/Echo"
        app_with_logger.register_unary_rpc(path, echo_handler, EchoRequest)

        scope = self.create_http_scope(path=path)
        # Disconnect during body reading
        receive = self.create_receive_with_disconnect(0.01)
        send = AsyncMock()

        # Should handle disconnect gracefully
        with pytest.raises(ConnectionError, match="Client disconnected"):
            await app_with_logger(scope, receive, send)

    @pytest.mark.asyncio
    async def test_receive_exception_handling(self, app_with_logger: ConnectASGI):
        """Test handling of exceptions during receive operations."""

        # Register a handler so request gets to body reading stage
        async def echo_handler(req: ClientRequest[EchoRequest]) -> ServerResponse[EchoResponse]:
            response = EchoResponse()
            response.message = f"echo: {req.msg.message}"
            return ServerResponse(response)

        path = "/test.Service/Method"
        app_with_logger.register_unary_rpc(path, echo_handler, EchoRequest)

        scope = self.create_http_scope(path=path)
        receive = self.create_receive_with_exception(RuntimeError("Receive failed"))
        send = AsyncMock()

        with pytest.raises(ConnectionError, match="Failed to receive request data"):
            await app_with_logger(scope, receive, send)

    @pytest.mark.asyncio
    async def test_error_logging_and_propagation(self, app_with_logger: ConnectASGI):
        """Test that errors are properly logged and propagated."""

        # Register a handler that raises an exception
        async def failing_handler(req: ClientRequest[EchoRequest]) -> ServerResponse[EchoResponse]:
            raise ValueError("Test handler error")

        path = "/testing.TestingService/Echo"
        app_with_logger.register_unary_rpc(path, failing_handler, EchoRequest)

        request_body = json.dumps({"message": "test"}).encode()

        async def receive():
            return {"type": "http.request", "body": request_body, "more_body": False}

        scope = self.create_http_scope(path=path)
        send = AsyncMock()

        # Should complete normally (error converted to Connect error response)
        await app_with_logger(scope, receive, send)

        # Should have sent error response
        calls = send.call_args_list
        assert len(calls) == 2  # start + body

        start_call = calls[0]
        assert start_call[0][0]["status"] == 500  # Internal error

    @pytest.mark.asyncio
    async def test_concurrent_error_handling(self, app_with_logger: ConnectASGI):
        """Test handling of errors in concurrent requests."""

        # Register handlers that sometimes fail
        async def maybe_failing_handler(
            req: ClientRequest[EchoRequest],
        ) -> ServerResponse[EchoResponse]:
            message = req.msg.message
            if "fail" in message:
                raise ValueError(f"Requested failure: {message}")

            response = EchoResponse()
            response.message = f"echo: {message}"
            return ServerResponse(response)

        path = "/testing.TestingService/Echo"
        app_with_logger.register_unary_rpc(path, maybe_failing_handler, EchoRequest)

        # Create mix of successful and failing requests
        tasks = []
        expected_results = []

        for i in range(5):
            message = f"fail-{i}" if i % 2 == 0 else f"success-{i}"
            expected_results.append("error" if "fail" in message else "success")

            async def make_request(msg: str):
                request_body = json.dumps({"message": msg}).encode()

                async def receive():
                    return {"type": "http.request", "body": request_body, "more_body": False}

                scope = self.create_http_scope(path=path)
                send = AsyncMock()

                await app_with_logger(scope, receive, send)

                # Check if it was an error response
                start_call = send.call_args_list[0]
                status = start_call[0][0]["status"]
                return "error" if status >= 400 else "success"

            task = asyncio.create_task(make_request(message))
            tasks.append(task)

        # Wait for all requests to complete
        results = await asyncio.gather(*tasks)

        # Verify expected success/failure pattern
        assert results == expected_results

    @pytest.mark.asyncio
    async def test_malformed_receive_data(self, app_with_logger: ConnectASGI):
        """Test handling of malformed ASGI receive data."""

        # Register a handler so request gets to body reading stage
        async def echo_handler(req: ClientRequest[EchoRequest]) -> ServerResponse[EchoResponse]:
            response = EchoResponse()
            response.message = f"echo: {req.msg.message}"
            return ServerResponse(response)

        path = "/test.Service/Method"
        app_with_logger.register_unary_rpc(path, echo_handler, EchoRequest)

        async def malformed_receive():
            # Return invalid ASGI message
            return {"type": "invalid.message.type"}

        scope = self.create_http_scope(path=path)
        send = AsyncMock()

        # Should handle malformed message gracefully and send error response
        await app_with_logger(scope, malformed_receive, send)

        # Should have sent error response (500 Internal Server Error)
        calls = send.call_args_list
        assert len(calls) == 2  # start + body

        start_call = calls[0]
        assert start_call[0][0]["status"] == 500  # Internal error
