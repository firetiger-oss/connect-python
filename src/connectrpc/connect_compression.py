from __future__ import annotations

import zlib
from collections.abc import Callable
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol


class Decompressor(Protocol):
    def decompress(self, data: bytes) -> bytes: ...


class Compressor(Protocol):
    def compress(self, data: bytes) -> bytes: ...
    def flush(self) -> bytes: ...


def compress_stream(stream: Iterable[bytes], compressor: Compressor) -> Iterable[bytes]:
    def compressed():
        for b in stream:
            yield compressor.compress(b)
        yield compressor.flush()

    return compressed()


@dataclass
class CompressionCodec:
    label: str
    compressor: Callable[[], Compressor]
    decompressor: Callable[[], Decompressor]


class IdentityCompressor:
    def compress(self, data: bytes) -> bytes:
        return data

    def flush(self) -> bytes:
        return b""


class IdentityDecompressor:
    def decompress(self, data: bytes) -> bytes:
        return data


IdentityCodec = CompressionCodec("identity", IdentityCompressor, IdentityDecompressor)


class GzipDecompressor:
    def __init__(self) -> None:
        self.decompressor = zlib.decompressobj(wbits=zlib.MAX_WBITS | 16)

    def decompress(self, data: bytes) -> bytes:
        return self.decompressor.decompress(data)


class GzipCompressor:
    def __init__(self) -> None:
        self.compressor = zlib.compressobj(wbits=zlib.MAX_WBITS | 16)

    def compress(self, data: bytes) -> bytes:
        return self.compressor.compress(data)

    def flush(self) -> bytes:
        return self.compressor.flush()


GzipCodec = CompressionCodec("gzip", GzipCompressor, GzipDecompressor)

SUPPORTED_COMPRESSIONS = {"identity": IdentityCodec, "gzip": GzipCodec}


try:
    import brotli

    class BrotliCompressor:
        def compress(self, data: bytes) -> bytes:
            return brotli.compress(data)

        def flush(self) -> bytes:
            return b""

    class BrotliDecompressor:
        def decompress(self, data: bytes) -> bytes:
            return brotli.decompress(data)

    BrotliCodec = CompressionCodec("br", BrotliCompressor, BrotliDecompressor)
    SUPPORTED_COMPRESSIONS["br"] = BrotliCodec

except ImportError:
    pass

# Lots of ways zstd might be available...
try:
    # Python 3.14 makes zstd available in the standard library
    from compression import zstd

    class ZstdCompressor:
        def __init__(self):
            self.compressor = zstd.ZstdCompressor()

        def compress(self, data: bytes) -> bytes:
            return self.compressor.compress(data)

        def flush(self) -> bytes:
            return self.compressor.flush()

    class ZstdDecompressor:
        def decompress(self, data: bytes) -> bytes:
            return zstd.decompress(data)

    ZstdCodec = CompressionCodec("zstd", ZstdCompressor, ZstdDecompressor)
    SUPPORTED_COMPRESSIONS["zstd"] = ZstdCodec

except ImportError:
    # Fallback to pyzstd if its available
    try:
        import pyzstd

        class ZstdCompressor:
            def __init__(self):
                self.compressor = pyzstd.ZstdCompressor()

            def compress(self, data: bytes) -> bytes:
                return self.compressor.compress(data)

            def flush(self) -> bytes:
                return self.compressor.flush()

        class ZstdDecompressor:
            def decompress(self, data: bytes) -> bytes:
                return pyzstd.decompress(data)

        ZstdCodec = CompressionCodec("zstd", ZstdCompressor, ZstdDecompressor)
        SUPPORTED_COMPRESSIONS["zstd"] = ZstdCodec

    except ImportError:
        pass


def load_compression(id: str) -> CompressionCodec:
    codec = SUPPORTED_COMPRESSIONS.get(id)
    if codec is None:
        codec = IdentityCodec
    return codec


def supported_compression(id: str) -> bool:
    return id in SUPPORTED_COMPRESSIONS


def supported_compressions() -> list[str]:
    return sorted(SUPPORTED_COMPRESSIONS.keys())
