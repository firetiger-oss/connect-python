from __future__ import annotations

import socket
import sys
import tempfile
from typing import TYPE_CHECKING
from typing import Any

from google.protobuf.any_pb2 import Any as ProtoAny
from multidict import CIMultiDict

from conformance import multidict_to_proto
from conformance import proto_to_exception
from conformance import read_size_delimited_message
from conformance import write_size_delimited_message
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
from connectrpc.errors import ConnectError
from connectrpc.errors import ConnectErrorCode
from connectrpc.server import ClientRequest
from connectrpc.server import ClientStream
from connectrpc.server import ServerResponse
from connectrpc.server import ServerStream
from connectrpc.server_asgi import ConnectASGI

if TYPE_CHECKING:
    from asgiref.typing import ASGIApplication


def asgi_conformance_service(implementation: ConformanceServiceProtocol) -> ASGIApplication:
    """Create ASGI conformance service application.

    This manually creates the ASGI service since the generator doesn't support ASGI yet.
    Later this will be replaced by generated code in Task 18.
    """
    app = ConnectASGI()
    app.register_unary_rpc(
        "/connectrpc.conformance.v1.ConformanceService/Unary", implementation.unary, UnaryRequest
    )
    # Note: For now only unary RPCs are supported, streaming will be added later
    app.register_unary_rpc(
        "/connectrpc.conformance.v1.ConformanceService/Unimplemented",
        implementation.unimplemented,
        UnimplementedRequest,
    )
    app.register_unary_rpc(
        "/connectrpc.conformance.v1.ConformanceService/IdempotentUnary",
        implementation.idempotent_unary,
        IdempotentUnaryRequest,
    )
    return app


class ConformanceServiceProtocol:
    """Protocol for conformance service implementation - mirrors the WSGI version."""

    async def unary(self, req: ClientRequest[UnaryRequest]) -> ServerResponse[UnaryResponse]:
        """Async unary RPC handler."""
        ...

    async def server_stream(
        self, req: ClientRequest[ServerStreamRequest]
    ) -> ServerStream[ServerStreamResponse]:
        """Async server streaming RPC handler."""
        ...

    async def client_stream(
        self, req: ClientStream[ClientStreamRequest]
    ) -> ServerResponse[ClientStreamResponse]:
        """Async client streaming RPC handler."""
        ...

    async def bidi_stream(
        self, req: ClientStream[BidiStreamRequest]
    ) -> ServerStream[BidiStreamResponse]:
        """Async bidirectional streaming RPC handler."""
        ...

    async def unimplemented(
        self, req: ClientRequest[UnimplementedRequest]
    ) -> ServerResponse[UnimplementedResponse]:
        """Async unimplemented RPC handler."""
        ...

    async def idempotent_unary(
        self, req: ClientRequest[IdempotentUnaryRequest]
    ) -> ServerResponse[IdempotentUnaryResponse]:
        """Async idempotent unary RPC handler."""
        ...


class Conformance:
    """ASGI conformance service implementation - async version of WSGI conformance service."""

    async def unary(self, req: ClientRequest[UnaryRequest]) -> ServerResponse[UnaryResponse]:
        req_msg_any = ProtoAny()
        req_msg_any.Pack(req.msg)

        req_info = ConformancePayload.RequestInfo(
            request_headers=multidict_to_proto(req.headers),
            timeout_ms=req.timeout.timeout_ms,
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
            import asyncio

            await asyncio.sleep(delay / 1000.0)

        if req.msg.response_definition.HasField("error"):
            err = proto_to_exception(req.msg.response_definition.error)
            err.add_detail(req_info, include_debug=True)
            return ServerResponse(err, headers, trailers)
        else:
            msg = UnaryResponse(
                payload=ConformancePayload(
                    request_info=req_info,
                    data=req.msg.response_definition.response_data,
                ),
            )
            return ServerResponse(msg, headers, trailers)

    async def server_stream(
        self, req: ClientRequest[ServerStreamRequest]
    ) -> ServerStream[ServerStreamResponse]:
        # Note: This will be implemented when server streaming is added to ConnectASGI
        raise ConnectError(
            ConnectErrorCode.UNIMPLEMENTED, "server streaming not yet implemented in ASGI"
        )

    async def client_stream(
        self, req: ClientStream[ClientStreamRequest]
    ) -> ServerResponse[ClientStreamResponse]:
        # Note: This will be implemented when client streaming is added to ConnectASGI
        raise ConnectError(
            ConnectErrorCode.UNIMPLEMENTED, "client streaming not yet implemented in ASGI"
        )

    async def bidi_stream(
        self, req: ClientStream[BidiStreamRequest]
    ) -> ServerStream[BidiStreamResponse]:
        # Note: This will be implemented when bidirectional streaming is added to ConnectASGI
        raise ConnectError(
            ConnectErrorCode.UNIMPLEMENTED, "bidirectional streaming not yet implemented in ASGI"
        )

    async def unimplemented(
        self, req: ClientRequest[UnimplementedRequest]
    ) -> ServerResponse[UnimplementedResponse]:
        raise ConnectError(ConnectErrorCode.UNIMPLEMENTED, "not implemented")

    async def idempotent_unary(
        self, req: ClientRequest[IdempotentUnaryRequest]
    ) -> ServerResponse[IdempotentUnaryResponse]:
        raise NotImplementedError


class ASGIServer:
    """ASGI server using uvicorn, similar to SocketGunicornApp for WSGI."""

    def __init__(self, app: ASGIApplication, sock: socket.socket, extra_config: dict[str, Any]):
        self.app = app
        self.sock = sock
        self.extra_config = extra_config
        self.server = None

    def run(self) -> None:
        """Run the ASGI server."""
        try:
            import uvicorn
        except ImportError as err:
            raise RuntimeError("uvicorn is required for ASGI conformance server") from err

        host, port = self.sock.getsockname()

        config = uvicorn.Config(
            self.app, host=host, port=port, log_level="error", access_log=False, **self.extra_config
        )
        server = uvicorn.Server(config)
        self.server = server

        server.run([self.sock])

    def shutdown(self) -> None:
        """Shutdown the server."""
        if self.server:
            self.server.should_exit = True


def create_bound_socket() -> tuple[socket.socket, int]:
    """Create and bind a socket, return socket and port - reuse from WSGI version."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", 0))  # Let OS pick port
    sock.listen(128)  # Set listen backlog

    port = sock.getsockname()[1]
    return sock, port


def prepare_async(sc_req: ServerCompatRequest) -> tuple[ServerCompatResponse, ASGIServer]:
    """Create the ASGI application, wrap it in a server, and build the ServerCompatResponse.

    Similar to prepare_sync but for ASGI.
    """
    app_impl = Conformance()
    asgi_app = asgi_conformance_service(app_impl)
    sock, port = create_bound_socket()

    cfg: dict[str, Any] = {}
    if sc_req.use_tls:
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".pem") as cert_file:
            cert_file.write(sc_req.server_creds.cert)
            cfg["ssl_certfile"] = cert_file.name

        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".pem") as key_file:
            key_file.write(sc_req.server_creds.key)
            cfg["ssl_keyfile"] = key_file.name

    server = ASGIServer(asgi_app, sock, cfg)

    response = ServerCompatResponse(host="127.0.0.1", port=port, pem_cert=sc_req.server_creds.cert)
    return response, server


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

            if mode == "sync":
                from conformance_server import prepare_sync

                response, server = prepare_sync(request)
                write_size_delimited_message(response.SerializeToString())
                server.run()
                return
            elif mode == "async":
                response, server = prepare_async(request)
                write_size_delimited_message(response.SerializeToString())
                server.run()
                return
            else:
                raise NotImplementedError

        except Exception as e:
            sys.stderr.write(f"Error processing request: {e}\n")
            sys.stderr.flush()
            break


if __name__ == "__main__":
    main(sys.argv[1])
