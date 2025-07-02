"""ASGI request processing for ConnectRPC server implementation.

This module provides async request processing classes for handling ASGI-based
ConnectRPC requests, including validation, decompression, and response handling.

"""

from __future__ import annotations

from typing import TYPE_CHECKING

from asgiref.typing import ASGIReceiveCallable
from asgiref.typing import ASGISendCallable
from asgiref.typing import HTTPScope
from multidict import CIMultiDict

from .connect_compression import CompressionCodec
from .connect_compression import load_compression
from .connect_compression import supported_compression
from .connect_compression import supported_compressions
from .connect_serialization import CONNECT_JSON_SERIALIZATION
from .connect_serialization import CONNECT_PROTOBUF_SERIALIZATION
from .connect_serialization import ConnectSerialization
from .errors import BareHTTPError
from .errors import ConnectError
from .errors import ConnectErrorCode
from .server_asgi_io import ASGIScope
from .server_asgi_io import AsyncRequestBodyReader
from .server_asgi_io import AsyncResponseSender
from .timeouts import ConnectTimeout

if TYPE_CHECKING:
    pass


class AsyncConnectRequest:
    """Base class for async Connect requests, enriching ASGI scope with
    streaming decompression and deserialization capabilities.

    This is the async equivalent of ConnectRequest, designed to work with
    ASGI's event-driven model instead of WSGI's synchronous approach.
    """

    def __init__(
        self,
        scope: ASGIScope,
        receive: ASGIReceiveCallable,
        send: ASGISendCallable,
        compression: CompressionCodec,
        serialization: ConnectSerialization,
        timeout: ConnectTimeout,
    ):
        self.scope = scope
        self.receive = receive
        self.send = send
        self.compression = compression
        self.serialization = serialization
        self.timeout = timeout

        # Provide convenient access to common scope attributes
        self.path = scope.path
        self.headers = scope.headers
        self.method = scope.method
        self.content_type = scope.content_type

        # Create body reader - used by both unary and streaming requests
        self._body_reader = AsyncRequestBodyReader(receive, scope.content_length)

    @classmethod
    async def from_asgi(
        cls,
        scope: HTTPScope,
        receive: ASGIReceiveCallable,
        send: ASGISendCallable,
    ) -> AsyncConnectRequest | None:
        """Create an async Connect request from ASGI scope, receive, and send.

        This method handles validation of the request and returns None if the
        request is invalid (with appropriate error responses sent via ASGI).

        Args:
            scope: ASGI HTTP scope containing request metadata
            receive: ASGI receive callable for reading request body
            send: ASGI send callable for sending responses

        Returns:
            AsyncConnectRequest instance or None if request is invalid
        """
        try:
            # Wrap the scope for convenient access
            asgi_scope = ASGIScope(scope)

            # Validate content type first - this can result in 415 responses
            serialization = cls.validate_content_type(asgi_scope)

            # Then validate other protocol elements
            cls.validate_connect_protocol_header(asgi_scope)

            compression = cls.validate_compression(asgi_scope)
            timeout = cls.validate_timeout(asgi_scope)

            return cls(asgi_scope, receive, send, compression, serialization, timeout)

        except BareHTTPError as e:
            # Handle bare HTTP errors (like 415)
            await cls._handle_bare_http_error(e, send)
            return None
        except ConnectError as e:
            # Handle Connect protocol errors
            await cls._handle_connect_error(e, send, asgi_scope.content_type)
            return None

    @classmethod
    async def _handle_bare_http_error(cls, error: BareHTTPError, send: ASGISendCallable) -> None:
        """Handle a BareHTTPError by sending a raw HTTP response via ASGI."""
        # Parse status line to get status code
        status_parts = error.status_line.split(" ", 1)
        status_code = int(status_parts[0])

        # Convert headers to ASGI format
        headers = [(k.encode(), v.encode()) for k, v in error.headers.items()]

        # Send response
        sender = AsyncResponseSender(send)
        await sender.send_start(status_code, headers)
        await sender.send_body(error.body, more_body=False)

    @classmethod
    async def _handle_connect_error(
        cls, error: ConnectError, send: ASGISendCallable, content_type: str
    ) -> None:
        """Handle a ConnectError by sending appropriate response via ASGI.

        This method should be overridden by subclasses to provide
        protocol-specific error handling.

        Args:
            error: The ConnectError to handle
            send: ASGI send callable for sending responses
            content_type: The request's content-type for response formatting
        """
        raise NotImplementedError("Subclasses must implement _handle_connect_error")

    @staticmethod
    def validate_compression(scope: ASGIScope) -> CompressionCodec:
        """Validate compression headers and return appropriate codec.

        Should be overridden by subclasses to handle protocol-specific compression.

        Args:
            scope: ASGI scope containing request metadata

        Returns:
            CompressionCodec instance

        Raises:
            ConnectError: If compression is invalid or unsupported
        """
        raise NotImplementedError("Subclasses must implement validate_compression")

    @staticmethod
    def validate_content_type(scope: ASGIScope) -> ConnectSerialization:
        """Validate content-type header and return appropriate serialization.

        Should be overridden by subclasses to handle protocol-specific content types.

        Args:
            scope: ASGI scope containing request metadata

        Returns:
            ConnectSerialization instance

        Raises:
            BareHTTPError: If content type is invalid (415 response)
        """
        raise NotImplementedError("Subclasses must implement validate_content_type")

    @staticmethod
    def validate_connect_protocol_header(scope: ASGIScope) -> None:
        """Validate the connect-protocol-version header.

        Args:
            scope: ASGI scope containing request metadata

        Raises:
            ConnectError: If header is missing or invalid
        """
        connect_protocol_version = scope.headers.get("connect-protocol-version")
        if connect_protocol_version is None:
            # Conformance tests currently break if we enforce the
            # protocol version header's presence.  See
            # https://github.com/connectrpc/conformance/issues/1007
            return

        if connect_protocol_version != "1":
            raise ConnectError(
                ConnectErrorCode.INVALID_ARGUMENT,
                "unsupported connect-protocol-version; only version 1 is supported",
            )

    @staticmethod
    def validate_timeout(scope: ASGIScope) -> ConnectTimeout:
        """Validate the connect-timeout-ms header.

        Args:
            scope: ASGI scope containing request metadata

        Returns:
            ConnectTimeout instance

        Raises:
            ConnectError: If header is malformed
        """
        timeout_ms_header = scope.headers.get("connect-timeout-ms")
        if timeout_ms_header is not None:
            try:
                timeout_ms = int(timeout_ms_header)
            except ValueError:
                raise ConnectError(
                    ConnectErrorCode.INVALID_ARGUMENT,
                    "connect-timeout-ms header must be an integer",
                ) from None
        else:
            timeout_ms = None
        return ConnectTimeout(timeout_ms)


class AsyncConnectUnaryRequest(AsyncConnectRequest):
    """Async Connect unary request with complete request body reading.

    This class handles unary RPC requests in the ASGI environment, reading
    the complete request body asynchronously and applying decompression.

    Unlike streaming requests, unary requests read the entire body at once
    and apply decompression to the complete body before deserialization.
    """

    def __init__(
        self,
        scope: ASGIScope,
        receive: ASGIReceiveCallable,
        send: ASGISendCallable,
        compression: CompressionCodec,
        serialization: ConnectSerialization,
        timeout: ConnectTimeout,
    ):
        super().__init__(scope, receive, send, compression, serialization, timeout)
        self._body: bytes | None = None

    async def read_body(self) -> bytes:
        """Read and return the complete decompressed request body.

        This method reads the entire body once, applies decompression if needed,
        and caches the result for subsequent calls.

        Returns:
            Complete decompressed request body as bytes

        Raises:
            ConnectionError: If client disconnects during reading
            ConnectError: If body size validation or decompression fails
        """
        if self._body is None:
            # Read the raw body
            raw_body = await self._body_reader.read_all()

            # Apply decompression if needed
            if self.compression.label == "identity":
                self._body = raw_body
            else:
                try:
                    decompressor = self.compression.decompressor()
                    self._body = decompressor.decompress(raw_body)

                    # Ensure decompressor is finished
                    if hasattr(decompressor, "eof") and not decompressor.eof:
                        raise ConnectError(
                            ConnectErrorCode.INVALID_ARGUMENT,
                            f"Incomplete {self.compression.label} compressed data",
                        )

                except Exception as e:
                    raise ConnectError(
                        ConnectErrorCode.INVALID_ARGUMENT,
                        f"Failed to decompress {self.compression.label} data: {e}",
                    ) from e

        return self._body

    @staticmethod
    def validate_compression(scope: ASGIScope) -> CompressionCodec:
        """Validate content-encoding header for unary requests.

        Args:
            scope: ASGI scope containing request metadata

        Returns:
            CompressionCodec instance

        Raises:
            ConnectError: If compression is unsupported
        """
        encoding = scope.headers.get("content-encoding", "identity")
        if not supported_compression(encoding):
            err_msg = f"content-encoding {encoding} is not supported. Supported values are {supported_compressions()}"
            raise ConnectError(ConnectErrorCode.UNIMPLEMENTED, err_msg)
        return load_compression(encoding)

    @staticmethod
    def validate_content_type(scope: ASGIScope) -> ConnectSerialization:
        """Validate content-type header for unary requests.

        Args:
            scope: ASGI scope containing request metadata

        Returns:
            ConnectSerialization instance

        Raises:
            BareHTTPError: If content type is unsupported
        """
        if scope.content_type == "application/proto":
            return CONNECT_PROTOBUF_SERIALIZATION
        elif scope.content_type == "application/json":
            return CONNECT_JSON_SERIALIZATION
        else:
            headers: CIMultiDict[str] = CIMultiDict()
            headers.add("Accept-Post", "application/json, application/proto")
            body = b""  # 415 responses typically have empty body
            raise BareHTTPError("415 Unsupported Media Type", headers, body)

    @classmethod
    async def _handle_connect_error(
        cls, error: ConnectError, send: ASGISendCallable, content_type: str
    ) -> None:
        """Handle ConnectError for unary requests."""
        # For unary requests, we always use the standard ConnectError response format
        await cls._send_connect_error_response(error, send)

    @classmethod
    async def _send_connect_error_response(
        cls, error: ConnectError, send: ASGISendCallable
    ) -> None:
        """Send a standard Connect error response via ASGI."""
        # Standard Connect error response
        status_code = error.http_status
        headers = [
            (b"content-type", b"application/json"),
        ]

        # Serialize error to JSON
        error_body = error.to_json().encode("utf-8")

        # Send response
        sender = AsyncResponseSender(send)
        await sender.send_start(status_code, headers)
        await sender.send_body(error_body, more_body=False)
