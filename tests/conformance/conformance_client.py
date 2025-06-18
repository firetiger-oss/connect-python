import asyncio
import struct
import sys
import traceback

import aiohttp

# Imported for their side effects of loading protobuf registry
import google.protobuf.descriptor_pb2  # noqa: F401
from google.protobuf.any_pb2 import Any
from multidict import CIMultiDict

from connectrpc.client import ConnectProtocol
from connectrpc.conformance.v1.client_compat_pb2 import ClientCompatRequest
from connectrpc.conformance.v1.client_compat_pb2 import ClientCompatResponse
from connectrpc.conformance.v1.client_compat_pb2 import ClientErrorResult
from connectrpc.conformance.v1.client_compat_pb2 import ClientResponseResult
from connectrpc.conformance.v1.config_pb2 import Code
from connectrpc.conformance.v1.config_pb2 import Codec
from connectrpc.conformance.v1.config_pb2 import Protocol
from connectrpc.conformance.v1.service_pb2 import BidiStreamRequest
from connectrpc.conformance.v1.service_pb2 import ClientStreamRequest
from connectrpc.conformance.v1.service_pb2 import Error
from connectrpc.conformance.v1.service_pb2 import Header
from connectrpc.conformance.v1.service_pb2 import ServerStreamRequest
from connectrpc.conformance.v1.service_pb2 import UnaryRequest
from connectrpc.conformance.v1.service_pb2 import UnimplementedRequest
from connectrpc.conformance.v1.service_pb2_connect import ConformanceServiceClient
from connectrpc.errors import ConnectError
from connectrpc.errors import ConnectErrorCode
from connectrpc.streams import StreamOutput
from connectrpc.unary import UnaryOutput


def debug(*args, **kwargs):
    #print(*args, **kwargs, file=sys.stderr)
    pass


async def handle(request: ClientCompatRequest) -> ClientCompatResponse:
    """Handle a ClientCompatRequest and return a blank ClientCompatResponse."""

    response = ClientCompatResponse()
    response.test_name = request.test_name
    debug("request: ", request)
    timeout_seconds: float | None = None
    if request.timeout_ms != 0:
        timeout_seconds = request.timeout_ms / 1000.0
    try:
        async with aiohttp.ClientSession() as http_session:
            if request.protocol != Protocol.PROTOCOL_CONNECT:
                raise NotImplementedError
            if request.codec == Codec.CODEC_JSON:
                protocol = ConnectProtocol.CONNECT_JSON
            elif request.codec == Codec.CODEC_PROTO:
                protocol = ConnectProtocol.CONNECT_PROTOBUF
            else:
                raise NotImplementedError

            client = ConformanceServiceClient(
                base_url="http://" + request.host + ":" + str(request.port),
                http_client=http_session,
                protocol=protocol,
            )

            extra_headers = request_headers(request)

            if request.method == "Unary":
                assert len(request.request_messages) == 1
                req_msg = request.request_messages[0]
                request_payload = UnaryRequest()

                assert req_msg.Is(request_payload.DESCRIPTOR)
                req_msg.Unpack(request_payload)

                response = ClientCompatResponse()
                response.test_name = request.test_name
                server_response = await client.call_unary(
                    request_payload,
                    extra_headers=extra_headers,
                    timeout_seconds=timeout_seconds,
                )
                result = result_from_unary_output(server_response)
                response.response.MergeFrom(result)

            elif request.method == "ServerStream":
                assert len(request.request_messages) == 1
                req_msg = request.request_messages[0]
                request_payload = ServerStreamRequest()
                assert req_msg.Is(request_payload.DESCRIPTOR)
                req_msg.Unpack(request_payload)

                stream_output = await client.call_server_stream(
                    request_payload,
                    extra_headers=extra_headers,
                    timeout_seconds=timeout_seconds,
                )
                result = await result_from_stream_output(stream_output)
                response.response.MergeFrom(result)

            elif request.method == "ClientStream":

                async def client_requests():
                    for msg in request.request_messages:
                        req_payload = ClientStreamRequest()
                        msg.Unpack(req_payload)
                        await asyncio.sleep(request.request_delay_ms / 1000.0)
                        yield req_payload
                stream_output = await client.call_client_stream(
                    client_requests(),
                    extra_headers=extra_headers,
                    timeout_seconds=timeout_seconds,
                )
                result = await result_from_stream_output(stream_output)
                response.response.MergeFrom(result)

            elif request.method == "BidiStream":

                async def client_requests():
                    for msg in request.request_messages:
                        req_payload = BidiStreamRequest()
                        msg.Unpack(req_payload)
                        await asyncio.sleep(request.request_delay_ms / 1000.0)
                        yield req_payload

                stream_output = await client.call_bidi_stream(
                    client_requests(),
                    extra_headers=extra_headers,
                    timeout_seconds=timeout_seconds,
                )
                result = await result_from_stream_output(stream_output)
                response.response.MergeFrom(result)

            elif request.method == "Unimplemented":
                # Same as Unary
                assert len(request.request_messages) == 1
                req_msg = request.request_messages[0]
                request_payload = UnimplementedRequest()

                assert req_msg.Is(request_payload.DESCRIPTOR)
                req_msg.Unpack(request_payload)

                response = ClientCompatResponse()
                response.test_name = request.test_name
                server_response = await client.call_unimplemented(
                    request_payload,
                    extra_headers=extra_headers,
                    timeout_seconds=timeout_seconds,
                )
                result = result_from_unary_output(server_response)
                response.response.MergeFrom(result)
            else:
                raise NotImplementedError(f"not implemented: {request.method}")

        debug("response: ", response)
        return response
    except Exception as error:
        debug("exceptional response: ", response)
        proto_err = exception_to_proto(error)
        response.response.error.MergeFrom(proto_err)
        return response


async def result_from_stream_output(stream_output: StreamOutput) -> ClientResponseResult:
    result = ClientResponseResult()
    async with stream_output as stream:
        async for server_msg in stream:
            result.payloads.append(server_msg.payload)

    resp_headers = multidict_to_proto(stream_output.response_headers())
    result.response_headers.extend(resp_headers)

    resp_trailers = stream_output.trailing_metadata()
    if resp_trailers is not None:
        resp_trailers_proto = [Header(name=k, value=v) for k, v in resp_trailers.items()]
        result.response_trailers.extend(resp_trailers_proto)

    if stream_output.error() is not None:
        result.error.CopyFrom(exception_to_proto(stream_output.error()))

    return result


def result_from_unary_output(unary_output: UnaryOutput) -> ClientResponseResult:
    result = ClientResponseResult()
    if unary_output.error() is not None:
        result.error.CopyFrom(exception_to_proto(unary_output.error()))
    if unary_output.message() is not None:
        result.payloads.append(unary_output.message().payload)

    resp_headers = multidict_to_proto(unary_output.response_headers())
    result.response_headers.extend(resp_headers)

    resp_trailers = unary_output.response_trailers()
    if resp_trailers is not None:
        resp_trailers_proto = multidict_to_proto(resp_trailers)
        result.response_trailers.extend(resp_trailers_proto)

    return result


def request_headers(req: ClientCompatRequest) -> CIMultiDict[str]:
    """Convert protobuf headers to CIMultiDict, preserving all values."""
    headers = CIMultiDict()
    for h in req.request_headers:
        for value in h.value:  # Preserve ALL values, not just the first one
            headers.add(h.name, value)
    return headers


def multidict_to_proto(headers: CIMultiDict) -> list[Header]:
    result = []
    for k in headers:
        result.append(Header(name=k, value=headers.getall(k)))
    return result


def exception_to_proto(error: Exception) -> Error:
    if isinstance(error, TimeoutError):
        error = ConnectError(ConnectErrorCode.DEADLINE_EXCEEDED, str(error))

    if not isinstance(error, ConnectError):
        tb = traceback.format_tb(error.__traceback__)
        error = ConnectError(ConnectErrorCode.INTERNAL, str(tb))

    details: list[Any] = []
    if isinstance(error.details, list):
        for d in error.details:
            v = Any()
            v.Pack(d.message())
            details.append(v)

    code = {
        ConnectErrorCode.CANCELED: Code.CODE_CANCELED,
        ConnectErrorCode.UNKNOWN: Code.CODE_UNKNOWN,
        ConnectErrorCode.INVALID_ARGUMENT: Code.CODE_INVALID_ARGUMENT,
        ConnectErrorCode.DEADLINE_EXCEEDED: Code.CODE_DEADLINE_EXCEEDED,
        ConnectErrorCode.NOT_FOUND: Code.CODE_NOT_FOUND,
        ConnectErrorCode.ALREADY_EXISTS: Code.CODE_ALREADY_EXISTS,
        ConnectErrorCode.PERMISSION_DENIED: Code.CODE_PERMISSION_DENIED,
        ConnectErrorCode.RESOURCE_EXHAUSTED: Code.CODE_RESOURCE_EXHAUSTED,
        ConnectErrorCode.FAILED_PRECONDITION: Code.CODE_FAILED_PRECONDITION,
        ConnectErrorCode.ABORTED: Code.CODE_ABORTED,
        ConnectErrorCode.OUT_OF_RANGE: Code.CODE_OUT_OF_RANGE,
        ConnectErrorCode.UNIMPLEMENTED: Code.CODE_UNIMPLEMENTED,
        ConnectErrorCode.INTERNAL: Code.CODE_INTERNAL,
        ConnectErrorCode.UNAVAILABLE: Code.CODE_UNAVAILABLE,
        ConnectErrorCode.DATA_LOSS: Code.CODE_DATA_LOSS,
        ConnectErrorCode.UNAUTHENTICATED: Code.CODE_UNAUTHENTICATED,
    }[error.code]

    return Error(code=code, message=error.message, details=details)


def read_size_delimited_message():
    """Read a size-delimited protobuf message from stdin."""
    # Read 4-byte big-endian length prefix
    length_bytes = sys.stdin.buffer.read(4)
    if len(length_bytes) < 4:
        return None  # EOF

    # Unpack big-endian 32-bit integer
    message_length = struct.unpack(">I", length_bytes)[0]

    # Read the actual message
    message_bytes = sys.stdin.buffer.read(message_length)
    if len(message_bytes) < message_length:
        raise ValueError("Incomplete message")

    return message_bytes


def write_size_delimited_message(message_bytes):
    """Write a size-delimited protobuf message to stdout."""
    # Write 4-byte big-endian length prefix
    length = len(message_bytes)
    sys.stdout.buffer.write(struct.pack(">I", length))

    # Write the actual message
    sys.stdout.buffer.write(message_bytes)
    sys.stdout.buffer.flush()


def main():
    """Main loop that reads requests from stdin and writes responses to stdout."""
    while True:
        try:
            message_bytes = read_size_delimited_message()
            if message_bytes is None:
                break  # EOF

            # Parse the request
            request = ClientCompatRequest()
            request.ParseFromString(message_bytes)

            # Handle the request
            response = asyncio.run(handle(request))

            # Write the response
            response_bytes = response.SerializeToString()
            write_size_delimited_message(response_bytes)

        except Exception as e:
            sys.stderr.write(f"Error processing request: {e}\n")
            sys.stderr.flush()
            break


if __name__ == "__main__":
    main()
