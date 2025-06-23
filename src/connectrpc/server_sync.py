from __future__ import annotations

import sys
from collections.abc import Callable
from collections.abc import Iterable
from enum import Enum
from typing import TYPE_CHECKING
from typing import Any
from typing import Generic
from typing import TypeVar

from google.protobuf.message import Message
from multidict import CIMultiDict

from .connect_compression import CompressionCodec
from .connect_compression import load_compression
from .connect_compression import supported_compression
from .connect_compression import supported_compressions
from .connect_serialization import CONNECT_JSON_SERIALIZATION
from .connect_serialization import CONNECT_PROTOBUF_SERIALIZATION
from .connect_serialization import ConnectSerialization
from .debugprint import debug
from .errors import ConnectError
from .errors import ConnectErrorCode
from .io import StreamReader

if TYPE_CHECKING:
    # wsgiref.types was added in Python 3.11.
    if sys.version_info >= (3, 11):
        from wsgiref.types import InputStream as WSGIInputStream
        from wsgiref.types import StartResponse
        from wsgiref.types import WSGIEnvironment
    else:
        from _typeshed.wsgi import InputStream as WSGIInputStream
        from _typeshed.wsgi import StartResponse
        from _typeshed.wsgi import WSGIEnvironment

T = TypeVar("T", bound=Message)
U = TypeVar("U", bound=Message)


class ClientRequest(Generic[T]):
    def __init__(
        self, msg: T, headers: CIMultiDict[str], trailers: CIMultiDict[str], timeout_ms: int | None
    ):
        self.msg = msg
        self.headers = headers
        self.trailers = trailers
        self.timeout_ms = timeout_ms


class ServerResponse(Generic[T]):
    def __init__(
        self,
        payload: T | ConnectError,
        headers: CIMultiDict[str] | None = None,
        trailers: CIMultiDict[str] | None = None,
    ):
        self.msg: T | None
        self.error: ConnectError | None
        if isinstance(payload, ConnectError):
            self.msg = None
            self.error = payload
        else:
            self.msg = payload
            self.error = None
        if headers is None:
            headers = CIMultiDict()
        self.headers = headers
        if trailers is None:
            trailers = CIMultiDict()
        self.trailers = trailers


class ClientStream(Generic[T]):
    def __init__(self, msgs: Iterable[T], headers: CIMultiDict[str], trailers: CIMultiDict[str]):
        self.msgs = msgs
        self.headers = headers
        self.trailers = trailers


class ServerStream(Generic[T]):
    def __init__(self, msgs: Iterable[T], headers: CIMultiDict[str], trailers: CIMultiDict[str]):
        self.msgs = msgs
        self.headers = headers
        self.trailers = trailers


UnaryRPC = Callable[[ClientRequest[T]], ServerResponse[U]]
ClientStreamingRPC = Callable[[ClientStream[T]], ServerResponse[U]]
ServerStreamingRPC = Callable[[ClientRequest[T]], ServerStream[U]]
BidiStreamingRPC = Callable[[ClientStream[T]], ServerStream[U]]


class RPCType(Enum):
    UNARY = 1
    CLIENT_STREAMING = 2
    SERVER_STREAMING = 3
    BIDI_STREAMING = 4


class WSGIRequest:
    READ_CHUNK_SIZE = 8192

    def __init__(self, environ: WSGIEnvironment):
        self.environ = environ
        self.headers: CIMultiDict[str] = CIMultiDict()
        for k, v in environ.items():
            if k.startswith("HTTP_"):
                # Unfortunately, WSGI rewrites incoming HTTP request
                # headers, replacing '-' with '_'. It probably
                # replaces other characters too. This is a best guess
                # on what to do.
                header_key = k[5:].replace("_", "-")
                self.headers.add(header_key, v)

        self.method = str(environ["REQUEST_METHOD"])
        self.path = str(environ["PATH_INFO"])
        self.content_type = environ.get("CONTENT_TYPE", "").lower()
        self.content_length = int(environ.get("CONTENT_LENGTH", 0) or 0)
        self.input: WSGIInputStream = environ["wsgi.input"]


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
        self.body = StreamReader(
            wsgi_req.input, compression.decompressor(), wsgi_req.content_length
        )
        self.compression = compression
        self.serialization = serialization
        self.timeout = timeout

        self.path = wsgi_req.path
        self.headers = wsgi_req.headers

    @classmethod
    def from_req(
        cls, req: WSGIRequest, resp: WSGIResponse, streaming: bool
    ) -> ConnectRequest | None:
        if not ConnectRequest.validate_connect_protocol_header(req, resp):
            return None

        compression = ConnectRequest.validate_compression(req, resp)
        if compression is None:
            return None

        serialization = ConnectRequest.validate_content_type(req, resp, streaming)
        if serialization is None:
            return None

        timeout = ConnectRequest.validate_timeout(req, resp)
        if timeout is None:
            return None

        return ConnectRequest(req, compression, serialization, timeout)

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
    def validate_compression(req: WSGIRequest, resp: WSGIResponse) -> CompressionCodec | None:
        encoding = req.headers.get("content-encoding", "identity")
        if not supported_compression(encoding):
            err_msg = f"content-encoding {encoding} is not supported. Supported values are {supported_compressions()}"
            err = ConnectError(ConnectErrorCode.UNIMPLEMENTED, err_msg)
            resp.set_from_error(err)
            return None
        return load_compression(encoding)

    @staticmethod
    def validate_content_type(
        req: WSGIRequest, resp: WSGIResponse, streaming: bool
    ) -> ConnectSerialization | None:
        if streaming:
            if not req.content_type.startsith("application/connect+"):
                resp.set_status_line("415 Unsupported Media Type")
                resp.set_header(
                    "Accept-Post", "application/connect+json, application/connect+proto"
                )
                return None

            if req.content_type == "application/connect+proto":
                serialization = CONNECT_PROTOBUF_SERIALIZATION
            elif req.content_type == "application/connect+json":
                serialization = CONNECT_JSON_SERIALIZATION
            else:
                err = ConnectError(
                    ConnectErrorCode.UNIMPLEMENTED,
                    f"{req.content_type} codec not implemented; only application/connect+proto and application/connect+json are supported",
                )
                resp.set_from_error(err)
                return None
        else:
            if req.content_type == "application/proto":
                serialization = CONNECT_PROTOBUF_SERIALIZATION
            elif req.content_type == "application/json":
                serialization = CONNECT_JSON_SERIALIZATION
            else:
                resp.set_status_line("415 Unsupported Media Type")
                resp.set_header("Accept-Post", "application/json, application/proto")
                return None
        return serialization

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


class ConnectTimeout:
    """
    Tiny wrapper to help distinguish between unset and invalid connect timeouts.
    """

    def __init__(self, timeout_ms: int | None):
        self.timeout_ms = timeout_ms


class WSGIResponse:
    """
    Lightweight wrapper to represent a WSGI HTTP response.
    """

    def __init__(self, start_response: StartResponse):
        self.start_response = start_response
        self.status_line = "200 OK"
        self.headers: CIMultiDict[str] = CIMultiDict()
        self.body: Iterable[bytes] = []

    def add_header(self, key: str, value: str) -> None:
        """
        Adds a header for key=value, appending to any existing header under that key.
        """
        self.headers.add(key, value)

    def set_header(self, key: str, value: str) -> None:
        """
        Set the header for key=value, overwriting any existing header under that key.
        """
        self.headers[key] = value

    def set_body(self, body: Iterable[bytes]) -> None:
        """
        Set the response body that will be sent.
        """
        self.body = body

    def set_status_line(self, status_line: str) -> None:
        """
        Set the HTTP Status-Line that will be set.
        """
        self.status_line = status_line

    def set_from_error(self, err: ConnectError) -> None:
        """
        Configure the WSGIResponse from a Connect error
        """
        self.set_status_line(err.code.http_status_line())
        body = err.to_json().encode()
        self.set_header("Content-Type", "application/json")
        self.set_header("Content-Encoding", "identity")
        self.set_header("Content-Length", str(len(body)))
        debug(body)
        self.set_body([body])

    def send_headers(self) -> None:
        headers = []
        for k, v in self.headers.items():
            headers.append((str(k), str(v)))
        self.start_response(self.status_line, headers)

    def send(self) -> Iterable[bytes]:
        self.send_headers()
        return self.body


class ConnectWSGI:
    def __init__(self) -> None:
        self.rpc_types: dict[str, RPCType] = {}
        self.unary_rpcs: dict[str, UnaryRPC[Any, Any]] = {}
        self.client_streaming_rpcs: dict[str, ClientStreamingRPC[Any, Any]] = {}
        self.server_streaming_rpcs: dict[str, ServerStreamingRPC[Any, Any]] = {}
        self.bidi_streaming_rpcs: dict[str, BidiStreamingRPC[Any, Any]] = {}
        self.rpc_input_types: dict[str, type[Message]] = {}

    def register_unary_rpc(
        self, path: str, fn: UnaryRPC[Any, Any], input_type: type[Message]
    ) -> None:
        self.rpc_types[path] = RPCType.UNARY
        self.unary_rpcs[path] = fn
        self.rpc_input_types[path] = input_type

    def register_client_streaming_rpc(
        self, path: str, fn: ClientStreamingRPC[Any, Any], input_type: type[Message]
    ) -> None:
        self.rpc_types[path] = RPCType.CLIENT_STREAMING
        self.client_streaming_rpcs[path] = fn
        self.rpc_input_types[path] = input_type

    def register_server_streaming_rpc(
        self, path: str, fn: ServerStreamingRPC[Any, Any], input_type: type[Message]
    ) -> None:
        self.rpc_types[path] = RPCType.SERVER_STREAMING
        self.server_streaming_rpcs[path] = fn
        self.rpc_input_types[path] = input_type

    def register_bidi_streaming_rpc(
        self, path: str, fn: BidiStreamingRPC[Any, Any], input_type: type[Message]
    ) -> None:
        self.rpc_types[path] = RPCType.BIDI_STREAMING
        self.bidi_streaming_rpcs[path] = fn
        self.rpc_input_types[path] = input_type

    def request_headers(self, environ: WSGIEnvironment) -> CIMultiDict[str]:
        result: CIMultiDict[str] = CIMultiDict()
        for k, v in environ.items():
            if k.startswith("HTTP_"):
                # Unfortunately, WSGI rewrites incoming HTTP request
                # headers, replacing '-' with '_'. It probably
                # replaces other characters too. This is a best guess
                # on what to do.
                header_key = k[5:].replace("_", "-")
                result.add(header_key, v)
        return result

    def __call__(self, environ: WSGIEnvironment, start_response: StartResponse) -> Iterable[bytes]:
        req = WSGIRequest(environ)
        resp = WSGIResponse(start_response)

        # First, ensure the method is valid.
        method = req.method
        if method != "POST":
            resp.set_status_line("405 Method Not Allowed")
            resp.add_header("Allow", "POST")
            return resp.send()

        # Now route the message.
        rpc_type = self.rpc_types.get(req.path)
        if rpc_type is None:
            err = ConnectError(ConnectErrorCode.NOT_FOUND, "no such rpc available")
            resp.set_from_error(err)
            return resp.send()

        try:
            if rpc_type == RPCType.UNARY:
                self.call_unary(req, resp)
            elif rpc_type == RPCType.CLIENT_STREAMING:
                self.call_client_streaming(req, resp)
            elif rpc_type == RPCType.SERVER_STREAMING:
                self.call_server_streaming(req, resp)
            elif rpc_type == RPCType.BIDI_STREAMING:
                self.call_bidi_streaming(req, resp)
            else:
                raise AssertionError("unreachable")
            return resp.send()

        except ConnectError as err:
            resp.set_from_error(err)
            return resp.send()
        except Exception as err:
            err = ConnectError(ConnectErrorCode.INTERNAL, str(err))
            import traceback

            debug("got exception: ", traceback.format_exc())
            err = ConnectError(ConnectErrorCode.INTERNAL, str(err))
            resp.set_from_error(err)
            return resp.send()

    def call_unary(self, req: WSGIRequest, resp: WSGIResponse) -> None:
        connect_req = ConnectRequest.from_req(req, resp, False)
        if connect_req is None:
            return
        del req

        msg_data = connect_req.body.readall()
        msg = connect_req.serialization.deserialize(
            bytes(msg_data), self.rpc_input_types[connect_req.path]
        )

        trailers: CIMultiDict[str] = CIMultiDict()
        for k, v in connect_req.headers.items():
            if k.startswith("trailer-"):
                trailers.add(k, v)

        client_req = ClientRequest(
            msg, connect_req.headers, trailers, connect_req.timeout.timeout_ms
        )

        server_resp = self.unary_rpcs[connect_req.path](client_req)

        for k, v in server_resp.headers.items():
            resp.add_header(k, v)
        for k, v in server_resp.trailers.items():
            resp.add_header("trailer-" + k, v)

        if server_resp.msg is not None:
            encoded = connect_req.serialization.serialize(server_resp.msg)
            resp.set_header("content-type", connect_req.serialization.unary_content_type)
            encoded = connect_req.compression.compressor().compress(encoded)
            resp.set_header("content-encoding", connect_req.compression.label)
            resp.set_header("content-length", str(len(encoded)))
            resp.set_body([encoded])
        elif server_resp.error is not None:
            resp.set_from_error(server_resp.error)
        else:
            raise RuntimeError("message and error cannot both be empty")
        return

    def call_client_streaming(self, req: WSGIRequest, resp: WSGIResponse) -> None:
        connect_req = ConnectRequest.from_req(req, resp, True)
        if connect_req is None:
            return None
        raise NotImplementedError

    def call_server_streaming(self, req: WSGIRequest, resp: WSGIResponse) -> None:
        connect_req = ConnectRequest.from_req(req, resp, True)
        if connect_req is None:
            return None
        raise NotImplementedError

    def call_bidi_streaming(self, req: WSGIRequest, resp: WSGIResponse) -> None:
        connect_req = ConnectRequest.from_req(req, resp, True)
        if connect_req is None:
            return None
        raise NotImplementedError
