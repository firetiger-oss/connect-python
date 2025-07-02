"""Tests for ConnectASGI server implementation."""

import asyncio
import json
import logging
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
        assert isinstance(app.rpc_input_types, dict)
        assert len(app.rpc_types) == 0
        assert len(app.unary_rpcs) == 0
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

        await app(scope, receive, mock_send)

        # Should send 400 Bad Request
        calls = mock_send.call_args_list
        assert len(calls) == 2

        start_call = calls[0]
        assert start_call[0][0]["type"] == "http.response.start"
        assert start_call[0][0]["status"] == 400

        body_call = calls[1]
        assert body_call[0][0]["type"] == "http.response.body"
        assert not body_call[0][0]["more_body"]

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
    async def test_streaming_not_implemented(self, app: ConnectASGI, mock_send: ASGISendCallable):
        """Test that streaming RPCs return 501 Not Implemented."""
        # Manually add a non-unary RPC type to test the not-implemented path
        path = "/test.Service/StreamingMethod"
        app.rpc_types[path] = RPCType.SERVER_STREAMING

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
