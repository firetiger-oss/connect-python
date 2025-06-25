from __future__ import annotations

import struct
from collections.abc import Iterable
from collections.abc import Iterator
from typing import Generic
from typing import TypeVar

from google.protobuf.message import Message
from multidict import CIMultiDict

from connectrpc.streams_connect import EndStreamResponse

from .connect_serialization import ConnectSerialization
from .errors import ConnectError
from .errors import ConnectErrorCode
from .server_requests import ConnectStreamingRequest
from .timeouts import ConnectTimeout

T = TypeVar("T", bound=Message)
U = TypeVar("U", bound=Message)


class ClientRequest(Generic[T]):
    """Represents a request sent from a client to a RPC method on the
    server. This is the type used for unary and server streaming RPCs.

    """

    def __init__(
        self, msg: T, headers: CIMultiDict[str], trailers: CIMultiDict[str], timeout: ConnectTimeout
    ):
        self.msg = msg
        self.headers = headers
        self.trailers = trailers
        self.timeout = timeout


class ServerResponse(Generic[T]):
    def __init__(
        self,
        payload: T | ConnectError | None,
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

    @classmethod
    def empty(cls) -> ServerResponse[T]:
        return ServerResponse(None)

    def payload(self) -> T | ConnectError:
        if self.msg is not None:
            return self.msg
        if self.error is not None:
            return self.error
        raise RuntimeError("invariant violated: ServerResponse has no payload")


class ClientStream(Generic[T]):
    def __init__(self, msgs: Iterator[T], headers: CIMultiDict[str], timeout: ConnectTimeout):
        self.msgs = msgs
        self.headers = headers
        self.timeout = timeout

    @classmethod
    def from_client_req(cls, req: ConnectStreamingRequest, msg_type: type[T]) -> ClientStream[T]:
        def message_iterator() -> Iterator[T]:
            while True:
                try:
                    envelope = req.body.readexactly(5)
                except EOFError:
                    return
                envelope_flags, msg_length = struct.unpack(">BI", envelope)
                data: bytes | bytearray = req.body.readexactly(msg_length)

                if envelope_flags & 1:
                    # Message is compressed - check if compression is expected
                    if req.compression.label == "identity":
                        raise ConnectError(
                            ConnectErrorCode.INTERNAL,
                            "received compressed message but no compression was specified in headers",
                        )
                    decompressor = req.compression.decompressor()
                    data = decompressor.decompress(bytes(data))
                elif req.compression.label != "identity":
                    # No compression flag but compression was specified - this might be OK
                    # Some implementations send uncompressed messages even when compression is available
                    pass

                msg = req.serialization.deserialize(bytes(data), msg_type)
                req.timeout.check()
                yield msg

        return ClientStream(message_iterator(), req.headers, req.timeout)

    def __iter__(self) -> Iterator[T]:
        return self.msgs


class ServerStream(Generic[T]):
    def __init__(
        self,
        msgs: Iterable[T | ConnectError],
        headers: CIMultiDict[str] | None = None,
        trailers: CIMultiDict[str] | None = None,
    ):
        self.msgs = msgs
        if headers is None:
            headers = CIMultiDict()
        self.headers = headers
        if trailers is None:
            trailers = CIMultiDict()
        self.trailers = trailers

    def iterate_bytes(self, ser: ConnectSerialization, timeout: ConnectTimeout) -> Iterator[bytes]:
        """Serialize the messages in self.msgs into a stream of
        bytes, suitable for wire transport by the connect streaming
        protocol.

        The timeout is checked after each message is yielded. If
        applications need to abort length operations at some other
        point, they should use self.timeout.

        """
        end_msg = EndStreamResponse(None, self.trailers)
        for msg in self.msgs:
            if isinstance(msg, ConnectError):
                end_msg.error = msg
                break
            data = ser.serialize(msg)
            envelope = struct.pack(">BI", 0, len(data))
            yield envelope + data

        data = end_msg.to_json()
        envelope = struct.pack(">BI", 2, len(data))
        yield envelope + data
