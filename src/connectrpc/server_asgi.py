"""ASGI server implementation for ConnectRPC.

This module provides the main ConnectASGI class that implements the ASGI
application interface for handling Connect protocol RPCs asynchronously.
"""

from __future__ import annotations

from collections.abc import Awaitable
from collections.abc import Callable
from typing import Any
from typing import TypeVar

from asgiref.typing import ASGI3Application
from asgiref.typing import ASGIReceiveCallable
from asgiref.typing import ASGISendCallable
from asgiref.typing import HTTPScope
from asgiref.typing import Scope
from asgiref.typing import WebSocketCloseEvent
from asgiref.typing import WebSocketScope
from google.protobuf.message import Message
from multidict import CIMultiDict

from .errors import ConnectError
from .errors import ConnectErrorCode
from .server import ClientRequest
from .server import ServerResponse
from .server_asgi_io import ASGIResponse
from .server_asgi_requests import AsyncConnectUnaryRequest
from .server_rpc_types import RPCType

T = TypeVar("T", bound=Message)
U = TypeVar("U", bound=Message)

# Type aliases for async RPC handlers

AsyncUnaryRPC = Callable[[ClientRequest[T]], Awaitable[ServerResponse[U]]]
# Note: Streaming RPC types will be added in later tasks


class ConnectASGI:
    """ASGI server for Connect protocol RPCs.

    This class implements the ASGI application interface and provides RPC
    registration methods similar to ConnectWSGI but designed for async operation.

    The server supports all four RPC types:
    - Unary: single request → single response
    - Client streaming: stream of requests → single response
    - Server streaming: single request → stream of responses
    - Bidirectional streaming: stream of requests → stream of responses

    Usage:
        app = ConnectASGI()
        app.register_unary_rpc("/service.Method", handler, RequestType)
    """

    def __init__(self) -> None:
        """Initialize a new ConnectASGI server."""
        # RPC registration storage, mirroring ConnectWSGI structure
        self.rpc_types: dict[str, RPCType] = {}
        self.unary_rpcs: dict[str, AsyncUnaryRPC[Message, Message]] = {}
        # Note: Other RPC type storage will be added in later tasks
        self.rpc_input_types: dict[str, type[Message]] = {}

    def register_unary_rpc(
        self, path: str, fn: AsyncUnaryRPC[Any, Any], input_type: type[Message]
    ) -> None:
        """Register a unary RPC handler.

        Args:
            path: RPC path (e.g., "/service.Service/Method")
            fn: Async handler function
            input_type: Protobuf message type for requests
        """
        self.rpc_types[path] = RPCType.UNARY
        self.unary_rpcs[path] = fn
        self.rpc_input_types[path] = input_type

    # Note: Other registration methods will be added in later tasks:
    # - register_client_streaming_rpc()
    # - register_server_streaming_rpc()
    # - register_bidi_streaming_rpc()

    async def __call__(
        self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable
    ) -> None:
        """ASGI application interface.

        This method handles incoming ASGI requests and routes them to the
        appropriate RPC handlers based on the request path and method.

        Args:
            scope: ASGI scope containing request metadata
            receive: ASGI receive callable for reading request body
            send: ASGI send callable for sending responses
        """
        # Create ASGIResponse wrapper early for consistent interface
        response = ASGIResponse(send)

        # Handle connection type - only HTTP is supported
        if scope["type"] == "websocket":
            await self._reject_websocket(scope, receive, send)
            return
        elif scope["type"] != "http":
            # Unknown scope type, reject with 400
            await self._send_error_response(
                400, "Bad Request", b"Unsupported ASGI scope type", response
            )
            return

        # Cast to HTTP scope for type checking
        http_scope: HTTPScope = scope

        # Validate HTTP method - only POST is supported
        method = http_scope["method"]
        if method != "POST":
            await self._send_error_response(
                405, "Method Not Allowed", b"", response, extra_headers=[(b"allow", b"POST")]
            )
            return

        # Route the request based on path
        path = http_scope["path"]
        rpc_type = self.rpc_types.get(path)
        if rpc_type is None:
            await self._send_error_response(404, "Not Found", b"", response)
            return

        # Dispatch to appropriate RPC handler
        try:
            if rpc_type == RPCType.UNARY:
                await self._handle_unary_rpc(http_scope, receive, response)
            else:
                # Streaming RPCs will be implemented in later tasks
                await self._send_error_response(
                    501, "Not Implemented", b"Streaming RPCs not yet implemented", response
                )
        except ConnectError as err:
            # Handle Connect protocol errors
            await self._handle_connect_error(err, response, rpc_type)
        except Exception as err:
            # Handle unexpected errors
            import traceback

            from .debugprint import debug

            debug("got exception: ", traceback.format_exc())
            connect_err = ConnectError(ConnectErrorCode.INTERNAL, str(err))
            await self._handle_connect_error(connect_err, response, rpc_type)

    async def _reject_websocket(
        self, scope: WebSocketScope, receive: ASGIReceiveCallable, send: ASGISendCallable
    ) -> None:
        """Reject WebSocket connections with a proper close."""
        close_event: WebSocketCloseEvent = {
            "type": "websocket.close",
            "code": 1002,  # Protocol error
            "reason": "",
        }
        await send(close_event)

    async def _send_error_response(
        self,
        status_code: int,
        reason_phrase: str,
        body: bytes,
        response: ASGIResponse,
        extra_headers: list[tuple[bytes, bytes]] | None = None,
    ) -> None:
        """Send a raw HTTP error response."""
        headers = [(b"content-type", b"text/plain")]
        if extra_headers:
            headers.extend(extra_headers)

        await response.send_start(status_code, headers)
        await response.send_body(body, more_body=False)

    async def _handle_connect_error(
        self, error: ConnectError, response: ASGIResponse, rpc_type: RPCType
    ) -> None:
        """Handle ConnectError by sending appropriate response format.

        Args:
            error: ConnectError to handle
            response: ASGIResponse for sending responses
            rpc_type: RPC type (affects error response format)
        """
        if rpc_type == RPCType.UNARY:
            # Unary errors use standard HTTP status + JSON body
            await self._send_connect_error_response(error, response)
        else:
            # Streaming errors will use HTTP 200 + EndStreamResponse format
            # This will be implemented in later tasks
            await self._send_connect_error_response(error, response)

    async def _send_connect_error_response(
        self, error: ConnectError, response: ASGIResponse
    ) -> None:
        """Send a standard Connect error response."""
        headers = [(b"content-type", b"application/json")]
        error_body = error.to_json().encode("utf-8")

        await response.send_start(error.http_status, headers)
        await response.send_body(error_body, more_body=False)

    async def _handle_unary_rpc(
        self, scope: HTTPScope, receive: ASGIReceiveCallable, response: ASGIResponse
    ) -> None:
        """Handle a unary RPC request.

        Args:
            scope: HTTP scope containing request metadata
            receive: ASGI receive callable for reading request body
            response: ASGIResponse for sending responses
        """
        # Create async Connect request with validation
        connect_req = await AsyncConnectUnaryRequest.from_asgi(scope, receive, response._send)
        if connect_req is None:
            # Validation failed, error response already sent
            return

        # Read and deserialize the request body
        body_data = await connect_req.read_body()
        msg = connect_req.serialization.deserialize(
            body_data, self.rpc_input_types[connect_req.path]
        )

        # Extract trailers from headers (headers starting with "trailer-")
        trailers: CIMultiDict[str] = CIMultiDict()
        for k, v in connect_req.headers.items():
            if k.startswith("trailer-"):
                trailers.add(k, v)

        # Create client request
        client_req = ClientRequest(msg, connect_req.headers, trailers, connect_req.timeout)

        # Call the RPC handler (await it since it's async)
        server_resp = await self.unary_rpcs[connect_req.path](client_req)

        # Send the response
        await self._send_unary_response(server_resp, connect_req, response)

    async def _send_unary_response(
        self,
        server_resp: ServerResponse[Message],
        connect_req: AsyncConnectUnaryRequest,
        response: ASGIResponse,
    ) -> None:
        """Send a unary RPC response.

        Args:
            server_resp: Server response to send
            connect_req: Original Connect request (for serialization context)
            response: ASGIResponse for sending responses
        """
        if server_resp.error is not None:
            # Send error response
            await self._send_connect_error_response(server_resp.error, response)
            return

        if server_resp.msg is None:
            # This shouldn't happen with well-formed responses
            error = ConnectError(
                ConnectErrorCode.INTERNAL, "Server response missing both message and error"
            )
            await self._send_connect_error_response(error, response)
            return

        # Serialize the response message
        response_data = connect_req.serialization.serialize(server_resp.msg)

        # Apply compression if needed
        if connect_req.compression.label != "identity":
            compressor = connect_req.compression.compressor()
            response_data = compressor.compress(response_data) + compressor.flush()

        # Prepare headers
        headers = [
            (b"content-type", connect_req.serialization.unary_content_type.encode()),
            (b"content-encoding", connect_req.compression.label.encode()),
        ]

        # Add server response headers (convert to lowercase for ASGI)
        for k, v in server_resp.headers.items():
            headers.append((k.lower().encode(), v.encode()))

        # Add trailers as headers with "trailer-" prefix (convert to lowercase for ASGI)
        for k, v in server_resp.trailers.items():
            headers.append((f"trailer-{k.lower()}".encode(), v.encode()))

        # Send response
        await response.send_start(200, headers)
        await response.send_body(response_data, more_body=False)


# Type alias for ASGI applications
ASGIApplication = ASGI3Application
