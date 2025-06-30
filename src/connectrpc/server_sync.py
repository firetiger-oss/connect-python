from __future__ import annotations

import struct
import sys
from collections.abc import Callable
from collections.abc import Iterable
from enum import Enum
from typing import TYPE_CHECKING
from typing import Any
from typing import TypeVar

from google.protobuf.message import Message
from multidict import CIMultiDict

from connectrpc.connect_compression import compress_stream
from connectrpc.debugprint import debug
from connectrpc.errors import ConnectError
from connectrpc.errors import ConnectErrorCode
from connectrpc.server import ClientRequest
from connectrpc.server import ClientStream
from connectrpc.server import ServerResponse
from connectrpc.server import ServerStream
from connectrpc.server_requests import ConnectStreamingRequest
from connectrpc.server_requests import ConnectUnaryRequest
from connectrpc.server_wsgi import WSGIRequest
from connectrpc.server_wsgi import WSGIResponse
from connectrpc.streams_connect import EndStreamResponse

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
        self.unary_rpcs: dict[str, UnaryRPC[Message, Message]] = {}
        self.client_streaming_rpcs: dict[str, ClientStreamingRPC[Message, Message]] = {}
        self.server_streaming_rpcs: dict[str, ServerStreamingRPC[Message, Message]] = {}
        self.bidi_streaming_rpcs: dict[str, BidiStreamingRPC[Message, Message]] = {}
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

    def _send_streaming_error(
        self, error: ConnectError, req: WSGIRequest, resp: WSGIResponse
    ) -> None:
        """Send a streaming error using HTTP 200 + EndStreamResponse format."""

        resp.set_status_line("200 OK")

        # Determine content-type from request
        if req.content_type.startswith("application/connect+"):
            resp.set_header("content-type", req.content_type)
        else:
            resp.set_header("content-type", "application/connect+json")

        # Send error as EndStreamResponse
        end_stream_response = EndStreamResponse(error, CIMultiDict())
        data = end_stream_response.to_json()
        envelope = struct.pack(">BI", 2, len(data))  # Flag 2 = EndStreamResponse
        resp.set_body([envelope + data])

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
            resp.set_status_line("404 Not Found")
            resp.set_body([])
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
            # Format error according to RPC type
            if rpc_type in (
                RPCType.CLIENT_STREAMING,
                RPCType.SERVER_STREAMING,
                RPCType.BIDI_STREAMING,
            ):
                # Streaming error: HTTP 200 + EndStreamResponse
                self._send_streaming_error(err, req, resp)
            else:
                # Unary error: HTTP status + JSON body
                resp.set_from_error(err)
            return resp.send()
        except Exception as err:
            import traceback

            debug("got exception: ", traceback.format_exc())
            connect_err = ConnectError(ConnectErrorCode.INTERNAL, str(err))
            # Format error according to RPC type
            if rpc_type in (
                RPCType.CLIENT_STREAMING,
                RPCType.SERVER_STREAMING,
                RPCType.BIDI_STREAMING,
            ):
                # Streaming error: HTTP 200 + EndStreamResponse
                self._send_streaming_error(connect_err, req, resp)
            else:
                # Unary error: HTTP status + JSON body
                resp.set_from_error(connect_err)
            return resp.send()

    def call_unary(self, req: WSGIRequest, resp: WSGIResponse) -> None:
        connect_req = ConnectUnaryRequest.from_req(req, resp)
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

        client_req = ClientRequest(msg, connect_req.headers, trailers, connect_req.timeout)

        server_resp = self.unary_rpcs[connect_req.path](client_req)

        for k, v in server_resp.headers.items():
            resp.add_header(k, v)
        for k, v in server_resp.trailers.items():
            resp.add_header("trailer-" + k, v)

        if server_resp.msg is not None:
            encoded = connect_req.serialization.serialize(server_resp.msg)
            resp.set_header("content-type", connect_req.serialization.unary_content_type)
            resp.set_header("content-encoding", connect_req.compression.label)
            resp.set_body(compress_stream([encoded], connect_req.compression.compressor()))
        elif server_resp.error is not None:
            resp.set_from_error(server_resp.error)
        else:
            raise RuntimeError("message and error cannot both be empty")
        return

    def call_client_streaming(self, req: WSGIRequest, resp: WSGIResponse) -> None:
        connect_req = ConnectStreamingRequest.from_req(req, resp)
        if connect_req is None:
            return None
        msg_type = self.rpc_input_types[connect_req.path]

        client_stream = ClientStream.from_client_req(connect_req, msg_type)

        server_response = self.client_streaming_rpcs[connect_req.path](client_stream)

        # The server responds with a stream with just one message.
        server_stream: ServerStream[Message] = ServerStream(
            [server_response.payload()], server_response.headers, server_response.trailers
        )

        resp.set_status_line("200 OK")
        for k, v in server_stream.headers.items():
            resp.add_header(k, v)
        resp.set_header("content-type", req.content_type)
        resp.set_header("connect-content-encoding", connect_req.compression.label)
        resp.set_body(server_stream.iterate_bytes(connect_req.serialization, connect_req.timeout))

    def call_server_streaming(self, req: WSGIRequest, resp: WSGIResponse) -> None:
        connect_req = ConnectStreamingRequest.from_req(req, resp)
        if connect_req is None:
            return None
        msg_type = self.rpc_input_types[connect_req.path]

        # The client sends the request as a stream with just one message.
        client_stream = ClientStream.from_client_req(connect_req, msg_type)
        last_msg: Message | None = None
        for i, msg in enumerate(client_stream):
            last_msg = msg
            if i >= 1:
                raise ConnectError(
                    ConnectErrorCode.UNIMPLEMENTED,
                    "server-streaming endpoint received more than one message from client",
                )

        if last_msg is None:
            raise ConnectError(
                ConnectErrorCode.UNIMPLEMENTED,
                "server-streaming endpoint received no message from client",
            )

        client_request = ClientRequest(
            last_msg, client_stream.headers, CIMultiDict(), client_stream.timeout
        )
        server_stream = self.server_streaming_rpcs[connect_req.path](client_request)

        connect_req.timeout.check()

        resp.set_status_line("200 OK")
        for k, v in server_stream.headers.items():
            resp.add_header(k, v)
        resp.set_header("content-type", req.content_type)
        resp.set_header("connect-content-encoding", connect_req.compression.label)
        resp.set_body(server_stream.iterate_bytes(connect_req.serialization, connect_req.timeout))

    def call_bidi_streaming(self, req: WSGIRequest, resp: WSGIResponse) -> None:
        connect_req = ConnectStreamingRequest.from_req(req, resp)
        if connect_req is None:
            return None
        msg_type = self.rpc_input_types[connect_req.path]

        client_stream = ClientStream.from_client_req(connect_req, msg_type)

        server_stream = self.bidi_streaming_rpcs[connect_req.path](client_stream)

        resp.set_status_line("200 OK")
        for k, v in server_stream.headers.items():
            resp.add_header(k, v)
        resp.set_header("content-type", req.content_type)
        resp.set_header("connect-content-encoding", connect_req.compression.label)
        resp.set_body(server_stream.iterate_bytes(connect_req.serialization, connect_req.timeout))
        return
