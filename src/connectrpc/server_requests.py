from __future__ import annotations

import sys
from abc import abstractmethod
from typing import TYPE_CHECKING
from typing import TypeVar

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
from .io import StreamReader
from .server_wsgi import WSGIRequest
from .server_wsgi import WSGIResponse
from .timeouts import ConnectTimeout

if TYPE_CHECKING:
    # wsgiref.types was added in Python 3.11.
    if sys.version_info >= (3, 11):
        pass
    else:
        pass

TConnectRequest = TypeVar("TConnectRequest", bound="ConnectRequest")


class ConnectRequest:
    """
    Enriches a plain WSGIRequest with streaming decompression and deserialization.
    """

    def __init__(
        self,
        wsgi_req: WSGIRequest,
        compression: CompressionCodec,
        serialization: ConnectSerialization,
        timeout: ConnectTimeout,
    ):
        self.compression = compression
        self.serialization = serialization
        self.timeout = timeout

        self.path = wsgi_req.path
        self.headers = wsgi_req.headers

    @classmethod
    def from_req(
        cls: type[TConnectRequest], req: WSGIRequest, resp: WSGIResponse
    ) -> TConnectRequest | None:
        try:
            # Validate content type first - this can result in 415 responses
            serialization = cls.validate_content_type(req)

            # Then validate other protocol elements
            ConnectRequest.validate_connect_protocol_header(req)

            compression = cls.validate_compression(req)
            timeout = ConnectRequest.validate_timeout(req)

            return cls(req, compression, serialization, timeout)
        except BareHTTPError as e:
            # Handle bare HTTP errors (like 415)
            cls._handle_bare_http_error(e, resp)
            return None
        except ConnectError as e:
            # Handle Connect protocol errors
            cls._handle_connect_error(e, resp, req.content_type)
            return None

    @classmethod
    def _handle_bare_http_error(cls, error: BareHTTPError, resp: WSGIResponse) -> None:
        """Handle a BareHTTPError by writing a raw HTTP response."""
        resp.set_status_line(error.status_line)
        for key, value in error.headers.items():
            resp.add_header(key, value)
        resp.set_body([error.body])

    @classmethod
    @abstractmethod
    def _handle_connect_error(
        cls, error: ConnectError, resp: WSGIResponse, content_type: str
    ) -> None:
        """Handle a ConnectError by writing appropriate response.

        This method should be overridden by subclasses to provide
        protocol-specific error handling.

        Args:
            error: The ConnectError to handle
            resp: The response object to write to
            content_type: The request's content-type for response formatting
        """
        ...

    @staticmethod
    @abstractmethod
    def validate_compression(req: WSGIRequest) -> CompressionCodec:
        """Should figure out the Compression codec to use, from headers.

        Raises ConnectError if compression is invalid.
        """
        ...

    @staticmethod
    @abstractmethod
    def validate_content_type(req: WSGIRequest) -> ConnectSerialization:
        """Should figure out the Serialization to use, from headers.

        Raises BareHTTPError if content type is invalid (415 response).
        """
        ...

    @staticmethod
    def validate_connect_protocol_header(req: WSGIRequest) -> None:
        """Make sure the connect-protocol-version header is set correctly.

        Raises ConnectError if header is missing or invalid.
        """
        connect_protocol_version = req.headers.get("connect-protocol-version")
        if connect_protocol_version is None:
            # Conformance tests currently break if we enforce the
            # protocol version header's presence.  See
            # https://github.com/connectrpc/conformance/issues/1007
            #
            # raise ConnectError(
            #     ConnectErrorCode.INVALID_ARGUMENT, "connect-protocol-version header must be set"
            # )
            return

        if connect_protocol_version != "1":
            raise ConnectError(
                ConnectErrorCode.INVALID_ARGUMENT,
                "unsupported connect-protocol-version; only version 1 is supported",
            )

    @staticmethod
    def validate_timeout(req: WSGIRequest) -> ConnectTimeout:
        """Validate the connect-timeout-ms header.

        Raises ConnectError if header is malformed.
        """
        timeout_ms_header = req.headers.get("connect-timeout-ms")
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


class ConnectUnaryRequest(ConnectRequest):
    def __init__(
        self,
        wsgi_req: WSGIRequest,
        compression: CompressionCodec,
        serialization: ConnectSerialization,
        timeout: ConnectTimeout,
    ):
        super().__init__(wsgi_req, compression, serialization, timeout)
        self.body = StreamReader(
            wsgi_req.input, compression.decompressor(), wsgi_req.content_length
        )

    @staticmethod
    def validate_compression(req: WSGIRequest) -> CompressionCodec:
        """Validate content-encoding header for unary requests.

        Raises ConnectError if compression is unsupported.
        """
        encoding = req.headers.get("content-encoding", "identity")
        if not supported_compression(encoding):
            err_msg = f"content-encoding {encoding} is not supported. Supported values are {supported_compressions()}"
            raise ConnectError(ConnectErrorCode.UNIMPLEMENTED, err_msg)
        return load_compression(encoding)

    @staticmethod
    def validate_content_type(req: WSGIRequest) -> ConnectSerialization:
        """Validate content-type header for unary requests.

        Raises BareHTTPError if content type is unsupported.
        """
        if req.content_type == "application/proto":
            return CONNECT_PROTOBUF_SERIALIZATION
        elif req.content_type == "application/json":
            return CONNECT_JSON_SERIALIZATION
        else:
            headers: CIMultiDict[str] = CIMultiDict()
            headers.add("Accept-Post", "application/json, application/proto")
            body = b""  # 415 responses typically have empty body
            raise BareHTTPError("415 Unsupported Media Type", headers, body)

    @classmethod
    def _handle_connect_error(
        cls, error: ConnectError, resp: WSGIResponse, content_type: str
    ) -> None:
        """Handle ConnectError for unary requests."""
        # For unary requests, we always use the standard ConnectError response format
        resp.set_from_error(error)


class ConnectStreamingRequest(ConnectRequest):
    def __init__(
        self,
        wsgi_req: WSGIRequest,
        compression: CompressionCodec,
        serialization: ConnectSerialization,
        timeout: ConnectTimeout,
    ):
        super().__init__(wsgi_req, compression, serialization, timeout)
        self.body = StreamReader(wsgi_req.input, None, 0)

    @staticmethod
    def validate_compression(req: WSGIRequest) -> CompressionCodec:
        """Validate connect-content-encoding header for streaming requests.

        Raises ConnectError if compression is unsupported.
        """
        stream_message_encoding = req.headers.get("connect-content-encoding", "identity")
        if not supported_compression(stream_message_encoding):
            err_msg = f"connect-content-encoding {stream_message_encoding} is not supported. Supported values are {supported_compressions()}"
            raise ConnectError(ConnectErrorCode.UNIMPLEMENTED, err_msg)
        return load_compression(stream_message_encoding)

    @staticmethod
    def validate_content_type(req: WSGIRequest) -> ConnectSerialization:
        """Validate content-type header for streaming requests.

        Raises BareHTTPError if content type is unsupported.
        """
        if not req.content_type.startswith("application/connect+"):
            headers: CIMultiDict[str] = CIMultiDict()
            headers.add("Accept-Post", "application/connect+json, application/connect+proto")
            body = b""  # 415 responses typically have empty body
            raise BareHTTPError("415 Unsupported Media Type", headers, body)

        if req.content_type == "application/connect+proto":
            return CONNECT_PROTOBUF_SERIALIZATION
        elif req.content_type == "application/connect+json":
            return CONNECT_JSON_SERIALIZATION
        else:
            raise ConnectError(
                ConnectErrorCode.UNIMPLEMENTED,
                f"{req.content_type} codec not implemented; only application/connect+proto and application/connect+json are supported",
            )

    @classmethod
    def _handle_connect_error(
        cls, error: ConnectError, resp: WSGIResponse, content_type: str
    ) -> None:
        """Handle ConnectError for streaming requests."""
        # Per Connect spec: streaming responses always have HTTP 200 OK
        # Errors are sent as EndStreamResponse with envelope flag 2
        import struct

        from connectrpc.streams_connect import EndStreamResponse

        resp.set_status_line("200 OK")

        # Use the request's content-type for the response
        if content_type.startswith("application/connect+"):
            resp.set_header("content-type", content_type)
        else:
            # Default to JSON if content-type was invalid
            resp.set_header("content-type", "application/connect+json")

        # Send error as EndStreamResponse
        end_stream_response = EndStreamResponse(error, CIMultiDict())
        data = end_stream_response.to_json()
        envelope = struct.pack(">BI", 2, len(data))  # Flag 2 = EndStreamResponse
        resp.set_body([envelope + data])
