from __future__ import annotations
import json

from typing import Generic, Type, TypeVar, Union, AsyncIterator, Optional, Any, Self
from collections.abc import Iterable
from dataclasses import dataclass

from google.protobuf.message import Message

T = TypeVar("T", bound=Message)
StreamInput = Union[AsyncIterator[T], Iterable[T]]


@dataclass
class StreamingError:
    code: str
    message: Optional[str]
    details: Optional[list[StreamingErrorDetail]]

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        details = None
        if "details" in data:
            details = [StreamingErrorDetail.from_dict(d) for d in data["details"]]
        return cls(
            code=data["code"],
            message=data.get("message"),
            details=details,
        )


@dataclass
class StreamingErrorDetail:
    type: str
    value: str
    debug: Optional[Any]

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(
            type=data["type"],
            value=data["value"],
            debug=data.get("debug"),
        )


@dataclass
class EndStreamResponse:
    error: Optional[StreamingError]
    metadata: Optional[dict[str, Any]]

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        data_dict = json.loads(data)

        val = cls(error=None, metadata=None)
        if "error" in data_dict:
            val.error = StreamingError.from_dict(data_dict["error"])

        if "metadata" in data_dict:
            val.metadata = data_dict["metadata"]

        return val
