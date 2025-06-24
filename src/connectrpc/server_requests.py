from __future__ import annotations

import sys
from abc import abstractmethod
from typing import TYPE_CHECKING
from typing import TypeVar

from .connect_compression import CompressionCodec
from .connect_compression import load_compression
from .connect_compression import supported_compression
from .connect_compression import supported_compressions
from .connect_serialization import CONNECT_JSON_SERIALIZATION
from .connect_serialization import CONNECT_PROTOBUF_SERIALIZATION
from .connect_serialization import ConnectSerialization
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
        if not ConnectRequest.validate_connect_protocol_header(req, resp):
            return None

        compression = cls.validate_compression(req, resp)
        if compression is None:
            return None

        serialization = cls.validate_content_type(req, resp)
        if serialization is None:
            return None

        timeout = cls.validate_timeout(req, resp)
        if timeout is None:
            return None

        return cls(req, compression, serialization, timeout)

    @staticmethod
    @abstractmethod
    def validate_compression(req: WSGIRequest, resp: WSGIResponse) -> CompressionCodec | None:
        """Should figure out the Compression codec to use, from headers"""
        ...

    @staticmethod
    @abstractmethod
    def validate_content_type(req: WSGIRequest, resp: WSGIResponse) -> ConnectSerialization | None:
        """Should figure out the Serialization to use, from headers"""
        ...

    @staticmethod
    def validate_connect_protocol_header(req: WSGIRequest, resp: WSGIResponse) -> bool:
        """Make sure the connect-protocol-version header is set
        correctly. Returns True if, else False. In the false case, it
        sets the response.

        """
        connect_protocol_version = req.headers.get("connect-protocol-version")
        if connect_protocol_version is None:
            err = ConnectError(
                ConnectErrorCode.INVALID_ARGUMENT, "connect-protocol-version header must be set"
            )
            resp.set_from_error(err)
            return False

        if connect_protocol_version != "1":
            err = ConnectError(
                ConnectErrorCode.INVALID_ARGUMENT,
                "unsupported connect-protocol-version; only version 1 is supported",
            )
            resp.set_from_error(err)
            return False
        return True

    @staticmethod
    def validate_timeout(req: WSGIRequest, resp: WSGIResponse) -> ConnectTimeout | None:
        timeout_ms_header = req.headers.get("connect-timeout-ms")
        if timeout_ms_header is not None:
            try:
                timeout_ms = int(timeout_ms_header)
            except ValueError:
                err = ConnectError(
                    ConnectErrorCode.INVALID_ARGUMENT,
                    "connect-timeout-ms header must be an integer",
                )
                resp.set_from_error(err)
                return None
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
    def validate_compression(req: WSGIRequest, resp: WSGIResponse) -> CompressionCodec | None:
        encoding = req.headers.get("content-encoding", "identity")
        if not supported_compression(encoding):
            err_msg = f"content-encoding {encoding} is not supported. Supported values are {supported_compressions()}"
            err = ConnectError(ConnectErrorCode.UNIMPLEMENTED, err_msg)
            resp.set_from_error(err)
            return None
        return load_compression(encoding)

    @staticmethod
    def validate_content_type(req: WSGIRequest, resp: WSGIResponse) -> ConnectSerialization | None:
        if req.content_type == "application/proto":
            return CONNECT_PROTOBUF_SERIALIZATION
        elif req.content_type == "application/json":
            return CONNECT_JSON_SERIALIZATION
        else:
            resp.set_status_line("415 Unsupported Media Type")
            resp.set_header("Accept-Post", "application/json, application/proto")
            return None


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
    def validate_compression(req: WSGIRequest, resp: WSGIResponse) -> CompressionCodec | None:
        stream_message_encoding = req.headers.get("connect-content-encoding", "identity")
        if not supported_compression(stream_message_encoding):
            err_msg = f"connect-content-encoding {stream_message_encoding} is not supported. Supported values are {supported_compressions()}"
            err = ConnectError(ConnectErrorCode.UNIMPLEMENTED, err_msg)
            resp.set_from_error(err)
            return None
        return load_compression(stream_message_encoding)

    @staticmethod
    def validate_content_type(req: WSGIRequest, resp: WSGIResponse) -> ConnectSerialization | None:
        if not req.content_type.startswith("application/connect+"):
            resp.set_status_line("415 Unsupported Media Type")
            resp.set_header("Accept-Post", "application/connect+json, application/connect+proto")
            return None

        if req.content_type == "application/connect+proto":
            return CONNECT_PROTOBUF_SERIALIZATION
        elif req.content_type == "application/connect+json":
            return CONNECT_JSON_SERIALIZATION
        else:
            err = ConnectError(
                ConnectErrorCode.UNIMPLEMENTED,
                f"{req.content_type} codec not implemented; only application/connect+proto and application/connect+json are supported",
            )
            resp.set_from_error(err)
            return None
