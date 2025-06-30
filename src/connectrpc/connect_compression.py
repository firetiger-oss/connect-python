from __future__ import annotations

import zlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol


class Decompressor(Protocol):
    def decompress(self, data: bytes) -> bytes: ...


class Compressor(Protocol):
    def compress(self, data: bytes) -> bytes: ...


@dataclass
class CompressionCodec:
    label: str
    compressor: Callable[[], Compressor]
    decompressor: Callable[[], Decompressor]


class IdentityCompressor:
    def compress(self, data: bytes) -> bytes:
        return data


class IdentityDecompressor:
    def decompress(self, data: bytes) -> bytes:
        return data


IdentityCodec = CompressionCodec("identity", IdentityCompressor, IdentityDecompressor)


class GzipDecompressor:
    def __init__(self) -> None:
        self.decompressor = zlib.decompressobj(zlib.MAX_WBITS | 16)

    def decompress(self, data: bytes) -> bytes:
        return self.decompressor.decompress(data)


class GzipCompressor:
    def __init__(self) -> None:
        self.compressor = zlib.compressobj(zlib.MAX_WBITS | 16)

    def compress(self, data: bytes) -> bytes:
        return self.compressor.compress(data)


GzipCodec = CompressionCodec("gzip", GzipCompressor, GzipDecompressor)

SUPPORTED_COMPRESSIONS = {"identity": IdentityCodec, "gzip": GzipCodec}


def load_compression(id: str) -> CompressionCodec:
    codec = SUPPORTED_COMPRESSIONS.get(id)
    if codec is None:
        codec = IdentityCodec
    return codec


def supported_compression(id: str) -> bool:
    return id in SUPPORTED_COMPRESSIONS


def supported_compressions() -> list[str]:
    return sorted(SUPPORTED_COMPRESSIONS.keys())
