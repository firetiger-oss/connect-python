from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from typing import TypeVar

from google.protobuf.message import Message

from connectrpc.errors import ConnectError

T = TypeVar("T", bound=Message)


@dataclass
class EndStreamResponse:
    error: ConnectError | None
    metadata: dict[str, Any] | None

    @classmethod
    def from_bytes(cls, data: bytes) -> EndStreamResponse:
        data_dict = json.loads(data)

        val = EndStreamResponse(error=None, metadata=None)
        if "error" in data_dict:
            val.error = ConnectError.from_dict(data_dict["error"])

        if "metadata" in data_dict:
            val.metadata = data_dict["metadata"]

        return val
