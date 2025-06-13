from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from typing import TypeVar

from google.protobuf.message import Message

T = TypeVar("T", bound=Message)


@dataclass
class StreamingError:
    code: str
    message: str | None
    details: list[StreamingErrorDetail] | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StreamingError:
        details = None
        if "details" in data:
            details = [StreamingErrorDetail.from_dict(d) for d in data["details"]]
        return StreamingError(
            code=data["code"],
            message=data.get("message"),
            details=details,
        )


@dataclass
class StreamingErrorDetail:
    type: str
    value: str
    debug: Any | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StreamingErrorDetail:
        return StreamingErrorDetail(
            type=data["type"],
            value=data["value"],
            debug=data.get("debug"),
        )


@dataclass
class EndStreamResponse:
    error: StreamingError | None
    metadata: dict[str, Any] | None

    @classmethod
    def from_bytes(cls, data: bytes) -> EndStreamResponse:
        data_dict = json.loads(data)

        val = EndStreamResponse(error=None, metadata=None)
        if "error" in data_dict:
            val.error = StreamingError.from_dict(data_dict["error"])

        if "metadata" in data_dict:
            val.metadata = data_dict["metadata"]

        return val
