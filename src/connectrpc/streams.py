from typing import Generic, Type, TypeVar, Union, AsyncIterator
from collections.abc import Iterable

from google.protobuf.message import Message

T = TypeVar("T", bound=Message)
StreamInput = Union[AsyncIterator[T], Iterable[T]]
