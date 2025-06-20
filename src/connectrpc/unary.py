from __future__ import annotations

from typing import Protocol
from typing import TypeVar

from google.protobuf.message import Message
from multidict import CIMultiDict

from .errors import ConnectError
from .errors import ConnectErrorCode
from .streams import AsyncStreamOutput
from .streams import StreamOutput

T = TypeVar("T", bound=Message, covariant=True)


class UnaryOutput(Protocol[T]):
    def message(self) -> T | None: ...

    def response_headers(self) -> CIMultiDict[str]: ...

    def response_trailers(self) -> CIMultiDict[str]: ...

    def error(self) -> ConnectError | None: ...


class ClientStreamingOutput(UnaryOutput[T]):
    """Server responses to client streaming requests must return
    exactly one message. We represent that as a UnaryOutput,
    constructed from a StreamingOutput.

    """

    def __init__(
        self,
        message: T | None,
        headers: CIMultiDict[str],
        trailers: CIMultiDict[str],
        error: ConnectError | None,
    ):
        self._message = message
        self._headers = headers
        self._trailers = trailers
        self._error = error

    @classmethod
    def from_stream_output(cls, stream_output: StreamOutput[T]) -> ClientStreamingOutput[T]:
        response: T | None = None
        error: ConnectError | None = None
        for msg in stream_output:
            if response is not None:
                # The server should only give us exactly one
                # response. If we got multiple, we should abort;
                # ignore trailers encoded in the stream.
                empty_trailers: CIMultiDict[str] = CIMultiDict()
                return cls(
                    message=None,
                    headers=stream_output.response_headers(),
                    trailers=empty_trailers,
                    error=ConnectError(
                        ConnectErrorCode.UNIMPLEMENTED,
                        "server responded with multiple messages; expecting exactly one",
                    ),
                )
            response = msg

        if response is None:
            error = stream_output.error()
            if error is None:
                error = ConnectError(
                    ConnectErrorCode.UNIMPLEMENTED,
                    "server responded with zero messages; expecting exactly one",
                )

        return cls(
            message=response,
            headers=stream_output.response_headers(),
            trailers=stream_output.response_trailers(),
            error=error,
        )

    @classmethod
    async def from_async_stream_output(
        cls, stream_output: AsyncStreamOutput[T]
    ) -> ClientStreamingOutput[T]:
        response: T | None = None
        error: ConnectError | None = None

        async with stream_output as stream:
            async for message in stream:
                if response is not None:
                    # The server should only give us exactly one
                    # response. If we got multiple, we should abort;
                    # ignore trailers encoded in the stream.
                    empty_trailers: CIMultiDict[str] = CIMultiDict()
                    return cls(
                        message=None,
                        headers=stream_output.response_headers(),
                        trailers=empty_trailers,
                        error=ConnectError(
                            ConnectErrorCode.UNIMPLEMENTED,
                            "server responded with multiple messages; expecting exactly one",
                        ),
                    )

                response = message

        if response is None:
            error = stream_output.error()
            if error is None:
                error = ConnectError(
                    ConnectErrorCode.UNIMPLEMENTED,
                    "server responded with zero messages; expecting exactly one",
                )

        return cls(
            message=response,
            headers=stream_output.response_headers(),
            trailers=stream_output.response_trailers(),
            error=error,
        )

    def message(self) -> T | None:
        return self._message

    def response_headers(self) -> CIMultiDict[str]:
        return self._headers

    def response_trailers(self) -> CIMultiDict[str]:
        return self._trailers

    def error(self) -> ConnectError | None:
        return self._error
