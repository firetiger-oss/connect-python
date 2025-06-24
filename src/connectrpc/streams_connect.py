from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TypeVar

from google.protobuf.message import Message
from multidict import CIMultiDict

from connectrpc.errors import ConnectError
from connectrpc.errors import ConnectErrorCode

T = TypeVar("T", bound=Message)


@dataclass
class EndStreamResponse:
    error: ConnectError | None
    metadata: CIMultiDict[str]

    def to_json(self) -> bytes:
        md: dict[str, list[str]] = {}
        for k, v in self.metadata.items():
            if k not in md:
                md[k] = []
            md[k].append(v)

        if self.error is None:
            if len(self.metadata) == 0:
                return b"{}"
            else:
                return json.dumps({"metadata": md}).encode()
        else:
            if len(self.metadata) == 0:
                return json.dumps({"error": self.error.to_dict()}).encode()
            else:
                return json.dumps({"error": self.error.to_dict(), "metadata": md}).encode()

    @classmethod
    def from_bytes(cls, data: bytes | bytearray) -> EndStreamResponse:
        data_dict = json.loads(data)

        val = EndStreamResponse(error=None, metadata=CIMultiDict())
        if "error" in data_dict and data_dict["error"] is not None:
            val.error = ConnectError.from_dict(data_dict["error"])

        if "metadata" in data_dict:
            md = data_dict["metadata"]
            if not isinstance(md, dict):
                val.error = ConnectError(
                    ConnectErrorCode.INTERNAL, "malformed trailer metadata received"
                )
                return val

            for k, v in md.items():
                if not isinstance(k, str):
                    val.error = ConnectError(
                        ConnectErrorCode.INTERNAL, "malformed trailer metadata received"
                    )
                    return val

                if not isinstance(v, list):
                    # Be a bit forgiving of this common error.
                    v = [v]

                for vv in v:
                    val.metadata.add(k, vv)

        return val
