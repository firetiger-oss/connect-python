from collections.abc import Iterable as _Iterable
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar

from google.protobuf import any_pb2 as _any_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf.internal import containers as _containers

from connectrpc.conformance.v1 import config_pb2 as _config_pb2

DESCRIPTOR: _descriptor.FileDescriptor

class UnaryResponseDefinition(_message.Message):
    __slots__ = (
        "response_headers",
        "response_data",
        "error",
        "response_trailers",
        "response_delay_ms",
        "raw_response",
    )
    RESPONSE_HEADERS_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_DATA_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_TRAILERS_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_DELAY_MS_FIELD_NUMBER: _ClassVar[int]
    RAW_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    response_headers: _containers.RepeatedCompositeFieldContainer[Header]
    response_data: bytes
    error: Error
    response_trailers: _containers.RepeatedCompositeFieldContainer[Header]
    response_delay_ms: int
    raw_response: RawHTTPResponse
    def __init__(
        self,
        response_headers: _Iterable[Header | _Mapping] | None = ...,
        response_data: bytes | None = ...,
        error: Error | _Mapping | None = ...,
        response_trailers: _Iterable[Header | _Mapping] | None = ...,
        response_delay_ms: int | None = ...,
        raw_response: RawHTTPResponse | _Mapping | None = ...,
    ) -> None: ...

class StreamResponseDefinition(_message.Message):
    __slots__ = (
        "response_headers",
        "response_data",
        "response_delay_ms",
        "error",
        "response_trailers",
        "raw_response",
    )
    RESPONSE_HEADERS_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_DATA_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_DELAY_MS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_TRAILERS_FIELD_NUMBER: _ClassVar[int]
    RAW_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    response_headers: _containers.RepeatedCompositeFieldContainer[Header]
    response_data: _containers.RepeatedScalarFieldContainer[bytes]
    response_delay_ms: int
    error: Error
    response_trailers: _containers.RepeatedCompositeFieldContainer[Header]
    raw_response: RawHTTPResponse
    def __init__(
        self,
        response_headers: _Iterable[Header | _Mapping] | None = ...,
        response_data: _Iterable[bytes] | None = ...,
        response_delay_ms: int | None = ...,
        error: Error | _Mapping | None = ...,
        response_trailers: _Iterable[Header | _Mapping] | None = ...,
        raw_response: RawHTTPResponse | _Mapping | None = ...,
    ) -> None: ...

class UnaryRequest(_message.Message):
    __slots__ = ("response_definition", "request_data")
    RESPONSE_DEFINITION_FIELD_NUMBER: _ClassVar[int]
    REQUEST_DATA_FIELD_NUMBER: _ClassVar[int]
    response_definition: UnaryResponseDefinition
    request_data: bytes
    def __init__(
        self,
        response_definition: UnaryResponseDefinition | _Mapping | None = ...,
        request_data: bytes | None = ...,
    ) -> None: ...

class UnaryResponse(_message.Message):
    __slots__ = ("payload",)
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    payload: ConformancePayload
    def __init__(self, payload: ConformancePayload | _Mapping | None = ...) -> None: ...

class IdempotentUnaryRequest(_message.Message):
    __slots__ = ("response_definition", "request_data")
    RESPONSE_DEFINITION_FIELD_NUMBER: _ClassVar[int]
    REQUEST_DATA_FIELD_NUMBER: _ClassVar[int]
    response_definition: UnaryResponseDefinition
    request_data: bytes
    def __init__(
        self,
        response_definition: UnaryResponseDefinition | _Mapping | None = ...,
        request_data: bytes | None = ...,
    ) -> None: ...

class IdempotentUnaryResponse(_message.Message):
    __slots__ = ("payload",)
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    payload: ConformancePayload
    def __init__(self, payload: ConformancePayload | _Mapping | None = ...) -> None: ...

class ServerStreamRequest(_message.Message):
    __slots__ = ("response_definition", "request_data")
    RESPONSE_DEFINITION_FIELD_NUMBER: _ClassVar[int]
    REQUEST_DATA_FIELD_NUMBER: _ClassVar[int]
    response_definition: StreamResponseDefinition
    request_data: bytes
    def __init__(
        self,
        response_definition: StreamResponseDefinition | _Mapping | None = ...,
        request_data: bytes | None = ...,
    ) -> None: ...

class ServerStreamResponse(_message.Message):
    __slots__ = ("payload",)
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    payload: ConformancePayload
    def __init__(self, payload: ConformancePayload | _Mapping | None = ...) -> None: ...

class ClientStreamRequest(_message.Message):
    __slots__ = ("response_definition", "request_data")
    RESPONSE_DEFINITION_FIELD_NUMBER: _ClassVar[int]
    REQUEST_DATA_FIELD_NUMBER: _ClassVar[int]
    response_definition: UnaryResponseDefinition
    request_data: bytes
    def __init__(
        self,
        response_definition: UnaryResponseDefinition | _Mapping | None = ...,
        request_data: bytes | None = ...,
    ) -> None: ...

class ClientStreamResponse(_message.Message):
    __slots__ = ("payload",)
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    payload: ConformancePayload
    def __init__(self, payload: ConformancePayload | _Mapping | None = ...) -> None: ...

class BidiStreamRequest(_message.Message):
    __slots__ = ("response_definition", "full_duplex", "request_data")
    RESPONSE_DEFINITION_FIELD_NUMBER: _ClassVar[int]
    FULL_DUPLEX_FIELD_NUMBER: _ClassVar[int]
    REQUEST_DATA_FIELD_NUMBER: _ClassVar[int]
    response_definition: StreamResponseDefinition
    full_duplex: bool
    request_data: bytes
    def __init__(
        self,
        response_definition: StreamResponseDefinition | _Mapping | None = ...,
        full_duplex: bool = ...,
        request_data: bytes | None = ...,
    ) -> None: ...

class BidiStreamResponse(_message.Message):
    __slots__ = ("payload",)
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    payload: ConformancePayload
    def __init__(self, payload: ConformancePayload | _Mapping | None = ...) -> None: ...

class UnimplementedRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class UnimplementedResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ConformancePayload(_message.Message):
    __slots__ = ("data", "request_info")
    class RequestInfo(_message.Message):
        __slots__ = ("request_headers", "timeout_ms", "requests", "connect_get_info")
        REQUEST_HEADERS_FIELD_NUMBER: _ClassVar[int]
        TIMEOUT_MS_FIELD_NUMBER: _ClassVar[int]
        REQUESTS_FIELD_NUMBER: _ClassVar[int]
        CONNECT_GET_INFO_FIELD_NUMBER: _ClassVar[int]
        request_headers: _containers.RepeatedCompositeFieldContainer[Header]
        timeout_ms: int
        requests: _containers.RepeatedCompositeFieldContainer[_any_pb2.Any]
        connect_get_info: ConformancePayload.ConnectGetInfo
        def __init__(
            self,
            request_headers: _Iterable[Header | _Mapping] | None = ...,
            timeout_ms: int | None = ...,
            requests: _Iterable[_any_pb2.Any | _Mapping] | None = ...,
            connect_get_info: ConformancePayload.ConnectGetInfo | _Mapping | None = ...,
        ) -> None: ...

    class ConnectGetInfo(_message.Message):
        __slots__ = ("query_params",)
        QUERY_PARAMS_FIELD_NUMBER: _ClassVar[int]
        query_params: _containers.RepeatedCompositeFieldContainer[Header]
        def __init__(
            self, query_params: _Iterable[Header | _Mapping] | None = ...
        ) -> None: ...

    DATA_FIELD_NUMBER: _ClassVar[int]
    REQUEST_INFO_FIELD_NUMBER: _ClassVar[int]
    data: bytes
    request_info: ConformancePayload.RequestInfo
    def __init__(
        self,
        data: bytes | None = ...,
        request_info: ConformancePayload.RequestInfo | _Mapping | None = ...,
    ) -> None: ...

class Error(_message.Message):
    __slots__ = ("code", "message", "details")
    CODE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    DETAILS_FIELD_NUMBER: _ClassVar[int]
    code: _config_pb2.Code
    message: str
    details: _containers.RepeatedCompositeFieldContainer[_any_pb2.Any]
    def __init__(
        self,
        code: _config_pb2.Code | str | None = ...,
        message: str | None = ...,
        details: _Iterable[_any_pb2.Any | _Mapping] | None = ...,
    ) -> None: ...

class Header(_message.Message):
    __slots__ = ("name", "value")
    NAME_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    name: str
    value: _containers.RepeatedScalarFieldContainer[str]
    def __init__(
        self, name: str | None = ..., value: _Iterable[str] | None = ...
    ) -> None: ...

class RawHTTPRequest(_message.Message):
    __slots__ = (
        "verb",
        "uri",
        "headers",
        "raw_query_params",
        "encoded_query_params",
        "unary",
        "stream",
    )
    class EncodedQueryParam(_message.Message):
        __slots__ = ("name", "value", "base64_encode")
        NAME_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        BASE64_ENCODE_FIELD_NUMBER: _ClassVar[int]
        name: str
        value: MessageContents
        base64_encode: bool
        def __init__(
            self,
            name: str | None = ...,
            value: MessageContents | _Mapping | None = ...,
            base64_encode: bool = ...,
        ) -> None: ...

    VERB_FIELD_NUMBER: _ClassVar[int]
    URI_FIELD_NUMBER: _ClassVar[int]
    HEADERS_FIELD_NUMBER: _ClassVar[int]
    RAW_QUERY_PARAMS_FIELD_NUMBER: _ClassVar[int]
    ENCODED_QUERY_PARAMS_FIELD_NUMBER: _ClassVar[int]
    UNARY_FIELD_NUMBER: _ClassVar[int]
    STREAM_FIELD_NUMBER: _ClassVar[int]
    verb: str
    uri: str
    headers: _containers.RepeatedCompositeFieldContainer[Header]
    raw_query_params: _containers.RepeatedCompositeFieldContainer[Header]
    encoded_query_params: _containers.RepeatedCompositeFieldContainer[
        RawHTTPRequest.EncodedQueryParam
    ]
    unary: MessageContents
    stream: StreamContents
    def __init__(
        self,
        verb: str | None = ...,
        uri: str | None = ...,
        headers: _Iterable[Header | _Mapping] | None = ...,
        raw_query_params: _Iterable[Header | _Mapping] | None = ...,
        encoded_query_params: _Iterable[RawHTTPRequest.EncodedQueryParam | _Mapping] | None = ...,
        unary: MessageContents | _Mapping | None = ...,
        stream: StreamContents | _Mapping | None = ...,
    ) -> None: ...

class MessageContents(_message.Message):
    __slots__ = ("binary", "text", "binary_message", "compression")
    BINARY_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    BINARY_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    COMPRESSION_FIELD_NUMBER: _ClassVar[int]
    binary: bytes
    text: str
    binary_message: _any_pb2.Any
    compression: _config_pb2.Compression
    def __init__(
        self,
        binary: bytes | None = ...,
        text: str | None = ...,
        binary_message: _any_pb2.Any | _Mapping | None = ...,
        compression: _config_pb2.Compression | str | None = ...,
    ) -> None: ...

class StreamContents(_message.Message):
    __slots__ = ("items",)
    class StreamItem(_message.Message):
        __slots__ = ("flags", "length", "payload")
        FLAGS_FIELD_NUMBER: _ClassVar[int]
        LENGTH_FIELD_NUMBER: _ClassVar[int]
        PAYLOAD_FIELD_NUMBER: _ClassVar[int]
        flags: int
        length: int
        payload: MessageContents
        def __init__(
            self,
            flags: int | None = ...,
            length: int | None = ...,
            payload: MessageContents | _Mapping | None = ...,
        ) -> None: ...

    ITEMS_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[StreamContents.StreamItem]
    def __init__(
        self, items: _Iterable[StreamContents.StreamItem | _Mapping] | None = ...
    ) -> None: ...

class RawHTTPResponse(_message.Message):
    __slots__ = ("status_code", "headers", "unary", "stream", "trailers")
    STATUS_CODE_FIELD_NUMBER: _ClassVar[int]
    HEADERS_FIELD_NUMBER: _ClassVar[int]
    UNARY_FIELD_NUMBER: _ClassVar[int]
    STREAM_FIELD_NUMBER: _ClassVar[int]
    TRAILERS_FIELD_NUMBER: _ClassVar[int]
    status_code: int
    headers: _containers.RepeatedCompositeFieldContainer[Header]
    unary: MessageContents
    stream: StreamContents
    trailers: _containers.RepeatedCompositeFieldContainer[Header]
    def __init__(
        self,
        status_code: int | None = ...,
        headers: _Iterable[Header | _Mapping] | None = ...,
        unary: MessageContents | _Mapping | None = ...,
        stream: StreamContents | _Mapping | None = ...,
        trailers: _Iterable[Header | _Mapping] | None = ...,
    ) -> None: ...
