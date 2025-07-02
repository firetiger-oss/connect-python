from typing import ClassVar as _ClassVar

from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message

DESCRIPTOR: _descriptor.FileDescriptor

class EchoRequest(_message.Message):
    __slots__ = ("message",)
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    message: str
    def __init__(self, message: str | None = ...) -> None: ...

class EchoResponse(_message.Message):
    __slots__ = ("message",)
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    message: str
    def __init__(self, message: str | None = ...) -> None: ...

class ErrorRequest(_message.Message):
    __slots__ = ("error_code", "error_message")
    ERROR_CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    error_code: str
    error_message: str
    def __init__(self, error_code: str | None = ..., error_message: str | None = ...) -> None: ...

class ErrorResponse(_message.Message):
    __slots__ = ("result",)
    RESULT_FIELD_NUMBER: _ClassVar[int]
    result: str
    def __init__(self, result: str | None = ...) -> None: ...

class HeaderRequest(_message.Message):
    __slots__ = ("message",)
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    message: str
    def __init__(self, message: str | None = ...) -> None: ...

class HeaderResponse(_message.Message):
    __slots__ = ("message",)
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    message: str
    def __init__(self, message: str | None = ...) -> None: ...

class DownloadRequest(_message.Message):
    __slots__ = ("message",)
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    message: str
    def __init__(self, message: str | None = ...) -> None: ...

class DownloadResponse(_message.Message):
    __slots__ = ("message", "sequence")
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    SEQUENCE_FIELD_NUMBER: _ClassVar[int]
    message: str
    sequence: int
    def __init__(self, message: str | None = ..., sequence: int | None = ...) -> None: ...

class UploadRequest(_message.Message):
    __slots__ = ("message", "sequence")
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    SEQUENCE_FIELD_NUMBER: _ClassVar[int]
    message: str
    sequence: int
    def __init__(self, message: str | None = ..., sequence: int | None = ...) -> None: ...

class UploadResponse(_message.Message):
    __slots__ = ("message",)
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    message: str
    def __init__(self, message: str | None = ...) -> None: ...

class ChatterRequest(_message.Message):
    __slots__ = ("message", "sequence")
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    SEQUENCE_FIELD_NUMBER: _ClassVar[int]
    message: str
    sequence: int
    def __init__(self, message: str | None = ..., sequence: int | None = ...) -> None: ...

class ChatterResponse(_message.Message):
    __slots__ = ("message", "sequence")
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    SEQUENCE_FIELD_NUMBER: _ClassVar[int]
    message: str
    sequence: int
    def __init__(self, message: str | None = ..., sequence: int | None = ...) -> None: ...
