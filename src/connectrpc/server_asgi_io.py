"""ASGI I/O primitives for ConnectRPC server implementation.

This module provides async I/O classes for handling ASGI events in
ConnectRPC servers.

"""

from asgiref.typing import ASGIReceiveCallable
from asgiref.typing import HTTPRequestEvent

from connectrpc.errors import ConnectError
from connectrpc.errors import ConnectErrorCode


class AsyncRequestBodyReader:
    """Async request body reader that handles ASGI http.request
    events.

    Unlike WSGI where the request body is available as a file-like
    object, ASGI delivers request bodies through multiple
    `http.request` events that must be accumulated until
    `more_body=False`.

    Provides both `read_all()` and `read_exactly(n)` methods for
    compatibility with existing ConnectRPC I/O patterns.

    """

    def __init__(self, receive: ASGIReceiveCallable, content_length: int | None = None):
        """
        Initialize the async request body reader.

        Args:
            receive: ASGI receive callable for getting http.request events
            content_length: Optional content-length header value for validation
        """
        self._receive = receive
        self._content_length = content_length
        self._buffer = bytearray()
        self._eof = False
        self._bytes_read = 0

    async def _ensure_data_available(self, min_bytes: int = 1) -> None:
        """
        Ensure at least min_bytes are available in the buffer.

        Reads from ASGI receive events until we have enough data or reach EOF.

        Args:
            min_bytes: Minimum number of bytes to ensure are available.
                      Use -1 to read until EOF (read all remaining data).

        Raises:
            EOFError: If EOF is reached before min_bytes are available
            ConnectionError: If client disconnects during reading
            RuntimeError: If unexpected ASGI message type is received
        """
        # Special case: -1 means read until EOF
        read_all = min_bytes == -1

        while (read_all or len(self._buffer) < min_bytes) and not self._eof:
            message = await self._receive()

            if message["type"] == "http.disconnect":
                raise ConnectionError("Client disconnected during request body reading")
            elif message["type"] != "http.request":
                raise RuntimeError(f"Unexpected ASGI message type: {message['type']}")

            # Type narrowing - we know it's HTTPRequestEvent now
            request_event: HTTPRequestEvent = message
            body = request_event["body"]
            more_body = request_event["more_body"]

            if body:
                self._buffer.extend(body)
                self._bytes_read += len(body)

                # Validate against content-length if provided
                if self._content_length is not None and self._bytes_read > self._content_length:
                    raise ConnectError(
                        ConnectErrorCode.INVALID_ARGUMENT,
                        f"Request body exceeds declared content-length: {self._bytes_read} > {self._content_length}",
                    )

            if not more_body:
                self._eof = True

                # Final validation against content-length
                if self._content_length is not None and self._bytes_read != self._content_length:
                    raise ConnectError(
                        ConnectErrorCode.INVALID_ARGUMENT,
                        f"Request body size mismatch: expected {self._content_length}, got {self._bytes_read}",
                    )

        # Only check for insufficient data if we're not reading all and not at EOF
        if not read_all and len(self._buffer) < min_bytes and self._eof:
            raise EOFError(
                f"Request body ended prematurely: needed {min_bytes} bytes, only {len(self._buffer)} available"
            )

    async def read_all(self) -> bytes:
        """
        Read the entire request body.

        Returns:
            Complete request body as bytes

        Raises:
            ConnectionError: If client disconnects during reading
            RuntimeError: If unexpected ASGI message type is received
        """
        # Read until EOF using -1 convention
        await self._ensure_data_available(-1)

        # Return all buffered data
        data = bytes(self._buffer)
        self._buffer.clear()
        return data

    async def read_exactly(self, n: int) -> bytes:
        """
        Read exactly n bytes from the request body.

        Args:
            n: Number of bytes to read

        Returns:
            Exactly n bytes from the request body

        Raises:
            EOFError: If EOF is reached before n bytes are available
            ConnectionError: If client disconnects during reading
            RuntimeError: If unexpected ASGI message type is received
        """
        if n == 0:
            return b""

        await self._ensure_data_available(n)

        # Extract exactly n bytes from the buffer
        data = bytes(self._buffer[:n])
        del self._buffer[:n]
        return data
