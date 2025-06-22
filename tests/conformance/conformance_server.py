import os
import ssl
import sys
import tempfile
from wsgiref.simple_server import WSGIRequestHandler
from wsgiref.simple_server import WSGIServer

from conformance import read_size_delimited_message
from conformance import write_size_delimited_message
from connectrpc.conformance.v1.config_pb2 import TLSCreds
from connectrpc.conformance.v1.server_compat_pb2 import ServerCompatRequest
from connectrpc.conformance.v1.server_compat_pb2 import ServerCompatResponse
from connectrpc.conformance.v1.service_pb2 import BidiStreamRequest
from connectrpc.conformance.v1.service_pb2 import BidiStreamResponse
from connectrpc.conformance.v1.service_pb2 import ClientStreamRequest
from connectrpc.conformance.v1.service_pb2 import ClientStreamResponse
from connectrpc.conformance.v1.service_pb2 import IdempotentUnaryRequest
from connectrpc.conformance.v1.service_pb2 import IdempotentUnaryResponse
from connectrpc.conformance.v1.service_pb2 import ServerStreamRequest
from connectrpc.conformance.v1.service_pb2 import ServerStreamResponse
from connectrpc.conformance.v1.service_pb2 import UnaryRequest
from connectrpc.conformance.v1.service_pb2 import UnaryResponse
from connectrpc.conformance.v1.service_pb2 import UnimplementedRequest
from connectrpc.conformance.v1.service_pb2 import UnimplementedResponse
from connectrpc.conformance.v1.service_pb2_connect import wsgi_conformance_service
from connectrpc.server_sync import ClientRequest
from connectrpc.server_sync import ClientStream
from connectrpc.server_sync import ServerResponse
from connectrpc.server_sync import ServerStream


class Conformance:
    def unary(self, req: ClientRequest[UnaryRequest]) -> ServerResponse[UnaryResponse]:
        raise NotImplementedError

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


def prepare_sync(sc_req: ServerCompatRequest) -> ServerCompatResponse:
    app = Conformance()
    wsgi_app = wsgi_conformance_service(app)
    server = WSGIServer(("127.0.0.1", 0), WSGIRequestHandler)
    server.set_app(wsgi_app)

    if sc_req.use_tls:
        ssl_context = create_ssl_context_from_tls_creds(sc_req.server_creds)
        pem_cert = sc_req.server_creds.cert
        server.socket = ssl_context.wrap_socket(server.socket, server_side=True)
    else:
        pem_cert = None

    address = server.socket.getsockname()
    response = ServerCompatResponse(host=address[0], port=address[1], pem_cert=pem_cert)

    return response


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

            # Parse the request
            request = ServerCompatRequest()
            request.ParseFromString(message_bytes)

            # Handle the request
            if mode == "async":
                raise NotImplementedError
            elif mode == "sync":
                response = prepare_sync(request)
            else:
                raise NotImplementedError

            write_size_delimited_message(response.SerializeToString())

        except Exception as e:
            sys.stderr.write(f"Error processing request: {e}\n")
            sys.stderr.flush()
            break


if __name__ == "__main__":
    main(sys.argv[1])
