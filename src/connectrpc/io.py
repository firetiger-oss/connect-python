from typing import Protocol

from .connect_compression import Decompressor


class Stream(Protocol):
    def read(self, size: int = ..., /) -> bytes: ...


class StreamReader:
    """Wrapper around a Stream which buffers reads, adds a readexactly
    method, and adds streaming decompression. These are all useful for
    reading streams from the Connect protocol.

    """

    READ_SIZE = 8192

    def __init__(self, src: Stream, decom: Decompressor | None, content_length: int = 0):
        self.src = src
        self.decom = decom
        self.buffer = bytearray()
        self.content_length = content_length
        self.bytes_read = 0

    def fill_buffer(self) -> bool:
        """Try to read from the source stream. Return False if the
        response has hit EOF

        """
        read_chunk = self._src_read(self.READ_SIZE)
        if not len(read_chunk):
            return False
        if self.decom is not None:
            read_chunk = self.decom.decompress(read_chunk)
        self.buffer.extend(read_chunk)
        return True

    def _src_read(self, n: int) -> bytes:
        if self.content_length > 0 and (n < 0 or ((self.bytes_read + n) > self.content_length)):
            n = self.content_length - self.bytes_read
        data = self.src.read(n)
        self.bytes_read += len(data)
        return data

    def readexactly(self, n: int) -> bytearray:
        while len(self.buffer) < n:
            if not self.fill_buffer():
                raise EOFError

        chunk = self.buffer[:n]
        del self.buffer[:n]
        return chunk

    def readall(self) -> bytearray:
        data = self._src_read(-1)
        if len(data) > 0 and self.decom is not None:
            data = self.decom.decompress(data)
            self.buffer.extend(data)
        return self.buffer

    def read(self, n: int) -> bytearray:
        if len(self.buffer) > n:
            self.fill_buffer()
        chunk = self.buffer[:n]
        del self.buffer[:n]
        return chunk
