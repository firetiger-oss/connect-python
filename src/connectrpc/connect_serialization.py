from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from google.protobuf.json_format import MessageToJson
from google.protobuf.json_format import Parse
from google.protobuf.message import Message

T = TypeVar("T", bound=Message)


class ConnectSerialization:
    def __init__(
        self,
        unary_content_type: str,
        streaming_content_type: str,
        serialize_fn: Callable[[Message], bytes],
        deserialize_fn: Callable[[bytes, type[T]], T],
    ):
        self.unary_content_type = unary_content_type
        self.streaming_content_type = streaming_content_type
        self._serialize_fn = serialize_fn
        self._deserialize_fn = deserialize_fn

    def serialize(self, msg: Message) -> bytes:
        return self._serialize_fn(msg)

    def deserialize(self, data: bytes, typ: type[T]) -> T:
        return self._deserialize_fn(data, typ)  # type: ignore[return-value,arg-type]


def _serialize_json(msg: Message) -> bytes:
    return MessageToJson(msg).encode("utf8")


def _deserialize_json(data: bytes, typ: type[T]) -> T:
    v = typ()
    Parse(data, v)
    return v


def _serialize_protobuf(msg: Message) -> bytes:
    return msg.SerializeToString()


def _deserialize_protobuf(data: bytes, typ: type[T]) -> T:
    v = typ()
    v.ParseFromString(data)
    return v


CONNECT_JSON_SERIALIZATION = ConnectSerialization(
    "application/json",
    "application/connect+json",
    _serialize_json,
    _deserialize_json,
)

CONNECT_PROTOBUF_SERIALIZATION = ConnectSerialization(
    "application/proto",
    "application/connect+proto",
    _serialize_protobuf,
    _deserialize_protobuf,
)
