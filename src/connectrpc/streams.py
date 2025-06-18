from __future__ import annotations

from collections.abc import AsyncIterator
from collections.abc import Iterable
from typing import Any
from typing import Protocol
from typing import TypeVar

from google.protobuf.message import Message
from multidict import MultiDict
from typing_extensions import Self

from .errors import ConnectError

T = TypeVar("T", bound=Message)
U = TypeVar("U", bound=Message, covariant=True)

StreamInput = AsyncIterator[T] | Iterable[T]


class StreamOutput(Protocol[U]):
    """Protocol for streaming response objects that manage connection resources.

    StreamOutput represents an async iterable that yields messages from a streaming
    RPC response. It provides two usage patterns for proper resource management:

    1. **Async Context Manager (Recommended)**:
       Automatically handles connection cleanup when exiting the context,
       even if iteration is stopped early:

       ```python
       async with client.call_server_streaming(url, req, ResponseType) as stream:
           async for response in stream:
               process(response)
               if should_stop:
                   break  # Connection automatically cleaned up
       ```

    2. **Explicit Cleanup**:
       Manual resource management when context manager isn't suitable:

       ```python
       stream = client.call_server_streaming(url, req, ResponseType)
       try:
           async for response in stream:
               process(response)
               if should_stop:
                   break
       finally:
           await stream.close()  # Explicit cleanup required
       ```

    ## For Implementers

    Implementations must:
    - Support async iteration protocol (__aiter__)
    - Provide trailing metadata access after consumption
    - Implement async context manager protocol for automatic cleanup
    - Provide explicit close() method for manual cleanup
    - Ensure connection resources are released exactly once
    - Handle cleanup on normal completion, early termination, and exceptions

    ## Connection Lifecycle

    - Connection resources (HTTP connections, sockets, etc.) should be acquired
      lazily when iteration begins
    - Resources must be released when:
      * Stream is fully consumed (normal completion)
      * Context manager exits (__aexit__)
      * close() method is called explicitly
      * An exception occurs during streaming
    - Resources should be returned to connection pools when possible (use
      release() rather than close() for HTTP connections)
    - Multiple calls to cleanup methods should be safe (idempotent)
    """

    def __aiter__(self) -> AsyncIterator[U]:
        """Return async iterator for the stream messages."""
        ...

    def response_headers(self) -> MultiDict[str]: ...

    def trailing_metadata(self) -> dict[str, Any] | None:
        """Get trailing metadata after stream is fully consumed.

        Returns:
            Dictionary of trailing metadata, or None if no metadata available.

        Raises:
            RuntimeError: If called before stream is fully consumed.
        """
        ...

    def done(self) -> bool:
        """Returns true when the stream has been fully consumed."""
        ...

    def error(self) -> ConnectError | None:
        """
        Returns any error encountered while reading the stream, if one exists.
        """
        ...

    async def __aenter__(self) -> Self:
        """Enter async context manager for automatic resource management."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit async context manager and clean up connection resources."""
        ...

    async def close(self) -> None:
        """Explicitly release connection resources.

        This method should be called when finished with the stream to ensure
        proper cleanup of underlying connections. Safe to call multiple times.

        Use this when not using the async context manager pattern:

        ```python
        stream = client.call_streaming(...)
        try:
            async for item in stream:
                process(item)
        finally:
            await stream.done()
        ```
        """
        ...
