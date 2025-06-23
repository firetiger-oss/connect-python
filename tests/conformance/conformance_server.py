import os
import socket
import ssl
import sys
import tempfile
import time
from wsgiref.simple_server import WSGIServer

from google.protobuf.any_pb2 import Any as ProtoAny
from gunicorn.app.base import BaseApplication
from multidict import CIMultiDict

from conformance import multidict_to_proto
from conformance import read_size_delimited_message
from conformance import write_size_delimited_message
from connectrpc.conformance.v1.config_pb2 import Code
from connectrpc.conformance.v1.config_pb2 import TLSCreds
from connectrpc.conformance.v1.server_compat_pb2 import ServerCompatRequest
from connectrpc.conformance.v1.server_compat_pb2 import ServerCompatResponse
from connectrpc.conformance.v1.service_pb2 import BidiStreamRequest
from connectrpc.conformance.v1.service_pb2 import BidiStreamResponse
from connectrpc.conformance.v1.service_pb2 import ClientStreamRequest
from connectrpc.conformance.v1.service_pb2 import ClientStreamResponse
from connectrpc.conformance.v1.service_pb2 import ConformancePayload
from connectrpc.conformance.v1.service_pb2 import IdempotentUnaryRequest
from connectrpc.conformance.v1.service_pb2 import IdempotentUnaryResponse
from connectrpc.conformance.v1.service_pb2 import ServerStreamRequest
from connectrpc.conformance.v1.service_pb2 import ServerStreamResponse
from connectrpc.conformance.v1.service_pb2 import UnaryRequest
from connectrpc.conformance.v1.service_pb2 import UnaryResponse
from connectrpc.conformance.v1.service_pb2 import UnimplementedRequest
from connectrpc.conformance.v1.service_pb2 import UnimplementedResponse
from connectrpc.conformance.v1.service_pb2_connect import wsgi_conformance_service
from connectrpc.debugprint import debug
from connectrpc.errors import ConnectError
from connectrpc.errors import ConnectErrorCode
from connectrpc.server_sync import ClientRequest
from connectrpc.server_sync import ClientStream
from connectrpc.server_sync import ServerResponse
from connectrpc.server_sync import ServerStream


class Conformance:
    def unary(self, req: ClientRequest[UnaryRequest]) -> ServerResponse[UnaryResponse]:
        req_msg_any = ProtoAny()
        req_msg_any.Pack(req.msg)

        req_info = ConformancePayload.RequestInfo(
            request_headers=multidict_to_proto(req.headers),
            timeout_ms=req.timeout_ms,
            requests=[req_msg_any],
        )

        headers: CIMultiDict[str] = CIMultiDict()
        for h in req.msg.response_definition.response_headers:
            for value in h.value:
                headers.add(h.name, value)

        trailers: CIMultiDict[str] = CIMultiDict()
        for t in req.msg.response_definition.response_trailers:
            for value in t.value:
                trailers.add(t.name, value)

        delay = req.msg.response_definition.response_delay_ms
        if delay > 0:
            time.sleep(delay / 1000.0)
        if req.msg.response_definition.HasField("error"):
            code = {
                Code.CODE_CANCELED: ConnectErrorCode.CANCELED,
                Code.CODE_UNKNOWN: ConnectErrorCode.UNKNOWN,
                Code.CODE_INVALID_ARGUMENT: ConnectErrorCode.INVALID_ARGUMENT,
                Code.CODE_DEADLINE_EXCEEDED: ConnectErrorCode.DEADLINE_EXCEEDED,
                Code.CODE_NOT_FOUND: ConnectErrorCode.NOT_FOUND,
                Code.CODE_ALREADY_EXISTS: ConnectErrorCode.ALREADY_EXISTS,
                Code.CODE_PERMISSION_DENIED: ConnectErrorCode.PERMISSION_DENIED,
                Code.CODE_RESOURCE_EXHAUSTED: ConnectErrorCode.RESOURCE_EXHAUSTED,
                Code.CODE_FAILED_PRECONDITION: ConnectErrorCode.FAILED_PRECONDITION,
                Code.CODE_ABORTED: ConnectErrorCode.ABORTED,
                Code.CODE_OUT_OF_RANGE: ConnectErrorCode.OUT_OF_RANGE,
                Code.CODE_UNIMPLEMENTED: ConnectErrorCode.UNIMPLEMENTED,
                Code.CODE_INTERNAL: ConnectErrorCode.INTERNAL,
                Code.CODE_UNAVAILABLE: ConnectErrorCode.UNAVAILABLE,
                Code.CODE_DATA_LOSS: ConnectErrorCode.DATA_LOSS,
                Code.CODE_UNAUTHENTICATED: ConnectErrorCode.UNAUTHENTICATED,
            }[req.msg.response_definition.error.code]
            details = ProtoAny()
            details.Pack(req_info)
            req_details = req.msg.response_definition.error.details
            req_details.append(details)
            err = ConnectError(code, req.msg.response_definition.error.message, req_details)
            return ServerResponse(err, headers, trailers)

        else:
            msg = UnaryResponse(
                payload=ConformancePayload(
                    request_info=req_info,
                    data=req.msg.response_definition.response_data,
                ),
            )
            return ServerResponse(msg, headers, trailers)

    def server_stream(
        self, req: ClientRequest[ServerStreamRequest]
    ) -> ServerStream[ServerStreamResponse]:
        raise NotImplementedError

    def client_stream(
        self, req: ClientStream[ClientStreamRequest]
    ) -> ServerResponse[ClientStreamResponse]:
        raise NotImplementedError

    def bidi_stream(self, req: ClientStream[BidiStreamRequest]) -> ServerStream[BidiStreamResponse]:
        raise NotImplementedError

    def unimplemented(
        self, req: ClientRequest[UnimplementedRequest]
    ) -> ServerResponse[UnimplementedResponse]:
        raise NotImplementedError

    def idempotent_unary(
        self, req: ClientRequest[IdempotentUnaryRequest]
    ) -> ServerResponse[IdempotentUnaryResponse]:
        raise NotImplementedError


class SocketGunicornApp(BaseApplication):
    def __init__(self, app, sock):
        self.app = app
        self.sock = sock
        super().__init__()

    def load_config(self):
        # Tell Gunicorn to use our pre-bound socket
        self.cfg.set("bind", f"fd://{self.sock.fileno()}")

    def load(self):
        return self.app


def create_bound_socket():
    """Create and bind a socket, return socket and port"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", 0))  # Let OS pick port
    sock.listen(128)  # Set listen backlog

    port = sock.getsockname()[1]
    return sock, port


def prepare_sync(sc_req: ServerCompatRequest) -> tuple[ServerCompatResponse, WSGIServer]:
    debug("received sync request", sc_req)
    app = Conformance()
    wsgi_app = wsgi_conformance_service(app)
    sock, port = create_bound_socket()
    server = SocketGunicornApp(wsgi_app, sock)

    response = ServerCompatResponse(host="127.0.0.1", port=port)
    debug(response)
    return response, server


def create_ssl_context_from_tls_creds(tls_creds: TLSCreds) -> ssl.SSLContext:
    """Create an SSLContext from TLSCreds protobuf message."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

    with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".pem") as cert_file:
        cert_file.write(tls_creds.cert)
        cert_path = cert_file.name

    with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".pem") as key_file:
        key_file.write(tls_creds.key)
        key_path = key_file.name

    try:
        context.load_cert_chain(cert_path, key_path)
    finally:
        os.unlink(cert_path)
        os.unlink(key_path)

    return context


def main(mode: str) -> None:
    """Main loop that reads requests from stdin and writes responses to stdout."""
    if mode not in {"sync", "async"}:
        raise ValueError("mode must be sync or async")
    while True:
        try:
            message_bytes = read_size_delimited_message()
            if message_bytes is None:
                break  # EOF

            request = ServerCompatRequest()
            request.ParseFromString(message_bytes)

            if mode == "async":
                raise NotImplementedError
            elif mode == "sync":
                response, server = prepare_sync(request)
            else:
                raise NotImplementedError

            write_size_delimited_message(response.SerializeToString())
            server.run()
            return

        except Exception as e:
            sys.stderr.write(f"Error processing request: {e}\n")
            sys.stderr.flush()
            break


if __name__ == "__main__":
    main(sys.argv[1])
