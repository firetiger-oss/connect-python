"""ASGI server implementation for ConnectRPC.

This module provides the main ConnectASGI class that implements the ASGI
application interface for handling Connect protocol RPCs asynchronously.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from collections.abc import Awaitable
from collections.abc import Callable
from typing import Any
from typing import TypeVar

from asgiref.typing import ASGI3Application
from asgiref.typing import ASGIReceiveCallable
from asgiref.typing import ASGISendCallable
from asgiref.typing import HTTPScope
from asgiref.typing import LifespanScope
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
from .server_asgi_streams import AsyncStreamingResponseSender
from .server_rpc_types import RPCType

T = TypeVar("T", bound=Message)
U = TypeVar("U", bound=Message)

# Type aliases for async RPC handlers

AsyncUnaryRPC = Callable[[ClientRequest[T]], Awaitable[ServerResponse[U]]]
AsyncServerStreamingRPC = Callable[[ClientRequest[T]], AsyncIterator[U]]


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

    def __init__(self, logger: logging.Logger | None = None) -> None:
        """Initialize a new ConnectASGI server.

        Args:
            logger: Optional logger instance. If None, creates a default logger.
        """
        # RPC registration storage, mirroring ConnectWSGI structure
        self.rpc_types: dict[str, RPCType] = {}
        self.unary_rpcs: dict[str, AsyncUnaryRPC[Message, Message]] = {}
        self.server_streaming_rpcs: dict[str, AsyncServerStreamingRPC[Message, Message]] = {}
        # Note: Client streaming and bidirectional streaming storage will be added in later tasks
        self.rpc_input_types: dict[str, type[Message]] = {}

        # Logging setup
        self._logger = logger or logging.getLogger("connectrpc.server_asgi")

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

    def register_server_streaming_rpc(
        self, path: str, fn: AsyncServerStreamingRPC[Any, Any], input_type: type[Message]
    ) -> None:
        """Register a server streaming RPC handler.

        Args:
            path: RPC path (e.g., "/service.Service/Method")
            fn: Async handler function that returns AsyncIterator[Message]
            input_type: Protobuf message type for requests
        """
        self.rpc_types[path] = RPCType.SERVER_STREAMING
        self.server_streaming_rpcs[path] = fn
        self.rpc_input_types[path] = input_type

    # Note: Other registration methods will be added in later tasks:
    # - register_client_streaming_rpc()
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
        if scope["type"] == "websocket":
            await self._reject_websocket(scope, receive, send)
            return
        elif scope["type"] == "lifespan":
            await self._handle_lifespan(scope, receive, send)
            return
        elif scope["type"] != "http":
            # Unknown scope type - can't create HTTP response, so just log and return
            self._logger.warning(f"Unsupported ASGI scope type: {scope['type']}")  # type:ignore[unreachable]
            return

        # Create ASGIResponse wrapper for HTTP requests
        response = ASGIResponse(send)
        rpc_type: RPCType | None = None

        try:
            # Cast to HTTP scope for type checking
            http_scope: HTTPScope = scope

            method = http_scope["method"]
            if method != "POST":
                self._logger.debug(f"Method not allowed: {method} (only POST supported)")
                await self._send_error_response(
                    405, "Method Not Allowed", b"", response, extra_headers=[(b"allow", b"POST")]
                )
                return

            path = http_scope["path"]
            rpc_type = self.rpc_types.get(path)
            if rpc_type is None:
                self._logger.debug(f"RPC path not found: {path}")
                await self._send_error_response(404, "Not Found", b"", response)
                return

            self._logger.debug(f"Routing {method} {path} to {rpc_type.name} RPC")

            # Dispatch to appropriate RPC handler
            if rpc_type == RPCType.UNARY:
                await self._handle_unary_rpc(http_scope, receive, response)
            elif rpc_type == RPCType.SERVER_STREAMING:
                await self._handle_server_streaming_rpc(http_scope, receive, response)
            else:
                self._logger.warning(f"Streaming RPC not yet implemented: {rpc_type}")
                await self._send_error_response(
                    501, "Not Implemented", b"Streaming RPCs not yet implemented", response
                )

        except ConnectError as err:
            # Handle Connect protocol errors
            self._logger.info(f"Connect protocol error: {err.code.name} - {err.message}")
            if not response.started:
                await self._handle_connect_error(err, response, rpc_type or RPCType.UNARY)
            else:
                self._logger.debug(
                    "Error occurred after streaming response started - handled by response sender"
                )
        except ConnectionError as err:
            self._logger.info(f"Connection error: {err}")
            # Don't try to send response on connection error - connection is likely dead
            raise
        except Exception as err:
            self._logger.error(f"Unexpected error processing request: {err}", exc_info=True)
            if not response.started:
                connect_err = ConnectError(ConnectErrorCode.INTERNAL, str(err))
                await self._handle_connect_error(connect_err, response, rpc_type or RPCType.UNARY)
            else:
                self._logger.debug(
                    "Error occurred after streaming response started - handled by response sender"
                )

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

    async def _handle_lifespan(
        self, scope: LifespanScope, receive: ASGIReceiveCallable, send: ASGISendCallable
    ) -> None:
        """Handle ASGI lifespan events (startup/shutdown)."""
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                try:
                    # Application startup - nothing to do for ConnectRPC
                    self._logger.debug("ASGI lifespan startup")
                    await send({"type": "lifespan.startup.complete"})
                except Exception as e:
                    self._logger.error(f"Error during startup: {e}")
                    await send({"type": "lifespan.startup.failed", "message": str(e)})
            elif message["type"] == "lifespan.shutdown":
                try:
                    # Application shutdown - nothing to do for ConnectRPC
                    self._logger.debug("ASGI lifespan shutdown")
                    await send({"type": "lifespan.shutdown.complete"})
                except Exception as e:
                    self._logger.error(f"Error during shutdown: {e}")
                    await send({"type": "lifespan.shutdown.failed", "message": str(e)})
                break

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
        self,
        error: ConnectError,
        response: ASGIResponse,
        custom_headers: CIMultiDict[str] | None = None,
        custom_trailers: CIMultiDict[str] | None = None,
    ) -> None:
        """Send a standard Connect error response."""
        headers = [(b"content-type", b"application/json")]

        # Add custom headers if provided
        if custom_headers is not None:
            for k, v in custom_headers.items():
                headers.append((k.lower().encode(), v.encode()))

        # Add custom trailers as headers with "trailer-" prefix
        if custom_trailers is not None:
            for k, v in custom_trailers.items():
                headers.append((f"trailer-{k.lower()}".encode(), v.encode()))

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
        path = scope["path"]

        try:
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
            self._logger.debug(f"Calling unary RPC handler for {path}")
            server_resp = await self.unary_rpcs[connect_req.path](client_req)

            # Send the response
            await self._send_unary_response(server_resp, connect_req, response)
            self._logger.debug(f"Successfully completed unary RPC for {path}")

        except ConnectionError:
            # Client disconnected - log and re-raise
            self._logger.info(f"Client disconnected during unary RPC processing for {path}")
            raise
        except ConnectError:
            # Connect protocol error - re-raise for upper handler
            raise
        except Exception as e:
            # Log unexpected handler errors with more context
            self._logger.error(f"Unary RPC handler error for {path}: {e}", exc_info=True)
            raise

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
            # Send error response with headers and trailers
            await self._send_connect_error_response(
                server_resp.error, response, server_resp.headers, server_resp.trailers
            )
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

    async def _handle_server_streaming_rpc(
        self, scope: HTTPScope, receive: ASGIReceiveCallable, response: ASGIResponse
    ) -> None:
        """Handle a server streaming RPC request.

        Server streaming RPCs receive a single request message and return a stream
        of response messages. This combines unary request processing with streaming
        response handling.

        Args:
            scope: HTTP scope containing request metadata
            receive: ASGI receive callable for reading request body
            response: ASGIResponse for sending responses
        """
        path = scope["path"]

        connect_req = await AsyncConnectUnaryRequest.from_asgi(scope, receive, response._send)
        if connect_req is None:
            return

        body_data = await connect_req.read_body()
        msg = connect_req.serialization.deserialize(
            body_data, self.rpc_input_types[connect_req.path]
        )

        trailers: CIMultiDict[str] = CIMultiDict()
        for k, v in connect_req.headers.items():
            if k.startswith("trailer-"):
                trailers.add(k, v)

        client_req = ClientRequest(msg, connect_req.headers, trailers, connect_req.timeout)

        self._logger.debug(f"Calling server streaming RPC handler for {path}")
        response_iterator = self.server_streaming_rpcs[connect_req.path](client_req)

        await self._send_server_streaming_response(response_iterator, connect_req, response)
        self._logger.debug(f"Successfully completed server streaming RPC for {path}")

    async def _send_server_streaming_response(
        self,
        response_iterator: AsyncIterator[Message],
        connect_req: AsyncConnectUnaryRequest,
        response: ASGIResponse,
    ) -> None:
        """Send a server streaming RPC response.

        Args:
            response_iterator: AsyncIterator of response messages from handler
            connect_req: Original Connect request (for serialization context)
            response: ASGIResponse for sending responses
        """
        content_type = connect_req.serialization.streaming_content_type

        headers = [
            (b"content-type", content_type.encode()),
            (b"connect-content-encoding", connect_req.compression.label.encode()),
        ]

        response_sender: AsyncStreamingResponseSender[Message] = AsyncStreamingResponseSender(
            response=response,
            serialization=connect_req.serialization,
            compression_codec=connect_req.compression,
        )

        await response_sender.send_stream(
            message_iterator=response_iterator,
            headers=headers,
            trailers=None,
        )


# Type alias for ASGI applications
ASGIApplication = ASGI3Application
