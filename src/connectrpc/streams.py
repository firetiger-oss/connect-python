from typing import Generic
from typing import TypeVar

T = TypeVar("T")


class ClientStream:
    pass


class ServerStream:
    pass


class Stream(Generic[T]):
    pass
