"""ASGI I/O primitives for ConnectRPC server implementation.

This module provides async I/O classes for handling ASGI events in
ConnectRPC servers.

"""

from typing import Any

from asgiref.typing import ASGIReceiveCallable
from asgiref.typing import ASGISendCallable
from asgiref.typing import HTTPRequestEvent
from asgiref.typing import HTTPResponseBodyEvent
from asgiref.typing import HTTPResponseStartEvent
from asgiref.typing import HTTPResponseTrailersEvent

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


class AsyncResponseSender:
    """Async response sender that implements ASGI response protocol.

    ASGI responses require sending `http.response.start` event followed by
    one or more `http.response.body` events. This class handles the ASGI
    protocol correctly and efficiently.

    Supports HTTP trailers by setting `trailers=True` in start event and
    sending trailers via separate `http.response.trailers` event.

    Can be used as an async context manager to ensure proper response completion.
    """

    def __init__(self, send: ASGISendCallable):
        """
        Initialize the async response sender.

        Args:
            send: ASGI send callable for sending response events
        """
        self._send = send
        self._started = False
        self._body_finished = False
        self._closed = False
        self._trailers_promised = False
        self._trailers_sent = False

    async def send_start(
        self, status: int, headers: list[tuple[bytes, bytes]], trailers: bool = False
    ) -> None:
        """
        Send the http.response.start event.

        Args:
            status: HTTP status code
            headers: List of header tuples (name, value) as bytes
            trailers: Whether HTTP trailers will be sent later

        Raises:
            RuntimeError: If start has already been sent or connection is closed
            ConnectionError: If client has disconnected
        """
        if self._started:
            raise RuntimeError("Response start has already been sent")
        if self._closed:
            raise RuntimeError("Connection is closed")

        self._trailers_promised = trailers

        start_event: HTTPResponseStartEvent = {
            "type": "http.response.start",
            "status": status,
            "headers": headers,
            "trailers": trailers,
        }

        try:
            await self._send(start_event)
            self._started = True
        except Exception as e:
            self._closed = True
            # Re-raise as ConnectionError for consistent error handling
            raise ConnectionError(f"Failed to send response start: {e}") from e

    async def send_body(self, data: bytes, more_body: bool = True) -> None:
        """
        Send an http.response.body event.

        Args:
            data: Response body data to send
            more_body: Whether more body events will follow

        Raises:
            RuntimeError: If start hasn't been sent or connection is closed
            ConnectionError: If client has disconnected
        """
        if not self._started:
            raise RuntimeError("Response start must be sent before body")
        if self._closed:
            raise RuntimeError("Connection is closed")
        if self._body_finished:
            raise RuntimeError("Response body has already been finished")

        body_event: HTTPResponseBodyEvent = {
            "type": "http.response.body",
            "body": data,
            "more_body": more_body,
        }

        try:
            await self._send(body_event)

            # Mark body as finished if this is the final body event
            if not more_body:
                self._body_finished = True

        except Exception as e:
            self._closed = True
            raise ConnectionError(f"Failed to send response body: {e}") from e

    async def send_trailers(self, trailers: list[tuple[bytes, bytes]]) -> None:
        """
        Send HTTP trailers via http.response.trailers event.

        This can only be called if trailers=True was set in send_start,
        and after the body has been finished.

        Args:
            trailers: List of trailer tuples (name, value) as bytes

        Raises:
            RuntimeError: If trailers weren't promised, body not finished, or already sent
            ConnectionError: If client has disconnected
        """
        if not self._trailers_promised:
            raise RuntimeError("Trailers not promised - must set trailers=True in send_start")
        if not self._body_finished:
            raise RuntimeError("Response body must be finished before sending trailers")
        if self._trailers_sent:
            raise RuntimeError("Trailers have already been sent")
        if self._closed:
            raise RuntimeError("Connection is closed")

        # Send trailers event
        trailers_event: HTTPResponseTrailersEvent = {
            "type": "http.response.trailers",
            "headers": trailers,
            "more_trailers": False,
        }

        try:
            await self._send(trailers_event)
            self._trailers_sent = True
            self._closed = True
        except Exception as e:
            self._closed = True
            raise ConnectionError(f"Failed to send response trailers: {e}") from e

    async def finish(self, trailers: list[tuple[bytes, bytes]] | None = None) -> None:
        """
        Finish the response by sending final body and trailers if needed.

        This method ensures proper response completion:
        - Sends final body event if not already sent
        - Sends trailers if they were promised but not yet sent

        Args:
            trailers: Optional trailers to send (empty list if None and trailers promised)

        Raises:
            ConnectionError: If client has disconnected
        """
        if self._closed:
            return  # Already finished

        # Send final body if not already sent
        if not self._body_finished:
            await self.send_body(b"", more_body=False)

        # Send trailers if promised
        if self._trailers_promised and not self._trailers_sent:
            # Send empty trailers if none provided
            await self.send_trailers(trailers or [])
        elif not self._trailers_promised:
            # No trailers promised, mark as closed
            self._closed = True

    async def __aenter__(self) -> "AsyncResponseSender":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit - ensures response is finished."""
        await self.finish()
