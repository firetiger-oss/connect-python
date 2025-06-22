from __future__ import annotations

import http
import sys
from collections.abc import Callable
from collections.abc import Iterable
from enum import Enum
from typing import TYPE_CHECKING
from typing import Any
from typing import Generic
from typing import TypeVar

from google.protobuf.message import Message

from .errors import ConnectError
from .errors import ConnectErrorCode

if TYPE_CHECKING:
    # wsgiref.types was added in Python 3.11.
    if sys.version_info >= (3, 11):
        from wsgiref.types import StartResponse
        from wsgiref.types import WSGIEnvironment
    else:
        from _typeshed.wsgi import StartResponse
        from _typeshed.wsgi import WSGIEnvironment

T = TypeVar("T", bound=Message)
U = TypeVar("U", bound=Message)


class ClientRequest(Generic[T]):
    def __init__(self, msg: T, headers: dict[str, str], trailers: dict[str, str]):
        self.msg = msg
        self.headers = headers
        self.trailers = trailers


class ServerResponse(Generic[T]):
    def __init__(self, msg: T, headers: dict[str, str], trailers: dict[str, str]):
        self.msg = msg
        self.headers = headers
        self.trailers = trailers


class ClientStream(Generic[T]):
    def __init__(self, msgs: Iterable[T], headers: dict[str, str], trailers: dict[str, str]):
        self.msgs = msgs
        self.headers = headers
        self.trailers = trailers


class ServerStream(Generic[T]):
    def __init__(self, msgs: Iterable[T], headers: dict[str, str], trailers: dict[str, str]):
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


class ConnectWSGI:
    def __init__(self) -> None:
        self.rpc_types: dict[str, RPCType] = {}
        self.unary_rpcs: dict[str, UnaryRPC[Any, Any]] = {}
        self.client_streaming_rpcs: dict[str, ClientStreamingRPC[Any, Any]] = {}
        self.server_streaming_rpcs: dict[str, ServerStreamingRPC[Any, Any]] = {}
        self.bidi_streaming_rpcs: dict[str, BidiStreamingRPC[Any, Any]] = {}

    def register_unary_rpc(self, path: str, fn: UnaryRPC[Any, Any]) -> None:
        self.rpc_types[path] = RPCType.UNARY
        self.unary_rpcs[path] = fn

    def register_client_streaming_rpc(self, path: str, fn: ClientStreamingRPC[Any, Any]) -> None:
        self.rpc_types[path] = RPCType.CLIENT_STREAMING
        self.client_streaming_rpcs[path] = fn

    def register_server_streaming_rpc(self, path: str, fn: ServerStreamingRPC[Any, Any]) -> None:
        self.rpc_types[path] = RPCType.SERVER_STREAMING
        self.server_streaming_rpcs[path] = fn

    def register_bidi_streaming_rpc(self, path: str, fn: BidiStreamingRPC[Any, Any]) -> None:
        self.rpc_types[path] = RPCType.BIDI_STREAMING
        self.bidi_streaming_rpcs[path] = fn

    def send_connect_error(
        self, start_response: StartResponse, headers: list[tuple[str, str]], err: ConnectError
    ) -> Iterable[bytes]:
        http_code = http.HTTPStatus(err.code.value[1])
        body = err.to_json().encode()
        # We're going to add Content-Length and Content-Type, so make
        # a copy of headers.
        headers = headers.copy()
        headers.append(("Content-Length", str(len(body))))
        headers.append(("Content-Type", "application/json"))
        status_line = f"{http_code.value} {http_code.phrase}"
        start_response(status_line, headers)
        return [body]

    def __call__(self, environ: WSGIEnvironment, start_response: StartResponse) -> Iterable[bytes]:
        method = environ["REQUEST_METHOD"]
        if method != "POST":
            start_response("405 Method Not Allowed", [("Allow", "POST")])
            return []

        path = environ["PATH_INFO"]
        rpc_type = self.rpc_types.get(path)
        if rpc_type is None:
            err = ConnectError(
                ConnectErrorCode.NOT_FOUND,
                "no such rpc available",
            )
            return self.send_connect_error(start_response, [], err)

        if rpc_type == RPCType.UNARY:
            return self.call_unary(environ, start_response, rpc=self.unary_rpcs[path])
        elif rpc_type == RPCType.CLIENT_STREAMING:
            return self.call_client_streaming(
                environ, start_response, self.client_streaming_rpcs[path]
            )
        elif rpc_type == RPCType.SERVER_STREAMING:
            return self.call_server_streaming(
                environ, start_response, self.server_streaming_rpcs[path]
            )
        elif rpc_type == RPCType.BIDI_STREAMING:
            return self.call_bidi_streaming(environ, start_response, self.bidi_streaming_rpcs[path])
        else:
            raise AssertionError("unreachable")

    def call_unary(
        self, environ: WSGIEnvironment, start_response: StartResponse, rpc: UnaryRPC[Any, Any]
    ) -> Iterable[bytes]:
        raise NotImplementedError

    def call_client_streaming(
        self,
        environ: WSGIEnvironment,
        start_response: StartResponse,
        rpc: ClientStreamingRPC[Any, Any],
    ) -> Iterable[bytes]:
        raise NotImplementedError

    def call_server_streaming(
        self,
        environ: WSGIEnvironment,
        start_response: StartResponse,
        rpc: ServerStreamingRPC[Any, Any],
    ) -> Iterable[bytes]:
        raise NotImplementedError

    def call_bidi_streaming(
        self,
        environ: WSGIEnvironment,
        start_response: StartResponse,
        rpc: BidiStreamingRPC[Any, Any],
    ) -> Iterable[bytes]:
        raise NotImplementedError
