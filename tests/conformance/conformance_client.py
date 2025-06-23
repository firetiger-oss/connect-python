import asyncio
import sys
import time
from collections.abc import AsyncGenerator
from collections.abc import Generator
from typing import Any

import aiohttp

# Imported for their side effects of loading protobuf registry
import google.protobuf.descriptor_pb2  # noqa: F401
import urllib3
import urllib3.exceptions
from multidict import MultiDict

from conformance import exception_to_proto
from conformance import multidict_to_proto
from conformance import read_size_delimited_message
from conformance import write_size_delimited_message
from connectrpc.client_protocol import ConnectProtocol
from connectrpc.conformance.v1.client_compat_pb2 import ClientCompatRequest
from connectrpc.conformance.v1.client_compat_pb2 import ClientCompatResponse
from connectrpc.conformance.v1.client_compat_pb2 import ClientResponseResult
from connectrpc.conformance.v1.config_pb2 import Codec
from connectrpc.conformance.v1.config_pb2 import Protocol
from connectrpc.conformance.v1.service_pb2 import BidiStreamRequest
from connectrpc.conformance.v1.service_pb2 import ClientStreamRequest
from connectrpc.conformance.v1.service_pb2 import ServerStreamRequest
from connectrpc.conformance.v1.service_pb2 import UnaryRequest
from connectrpc.conformance.v1.service_pb2 import UnimplementedRequest
from connectrpc.conformance.v1.service_pb2_connect import AsyncConformanceServiceClient
from connectrpc.conformance.v1.service_pb2_connect import ConformanceServiceClient
from connectrpc.debugprint import debug
from connectrpc.streams import AsyncStreamOutput
from connectrpc.streams import StreamOutput
from connectrpc.unary import UnaryOutput


def handle_sync(request: ClientCompatRequest) -> ClientCompatResponse:
    response = ClientCompatResponse()
    response.test_name = request.test_name
    debug("request: ", request)
    timeout_seconds: float | None = None
    if request.timeout_ms != 0:
        timeout_seconds = request.timeout_ms / 1000.0
    debug("request timeout: ", timeout_seconds)
    try:
        with urllib3.PoolManager() as http_client:
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
                http_client=http_client,
                protocol=protocol,
            )

            extra_headers = request_headers(request)
            request_payload: Any

            if request.method == "Unary":
                assert len(request.request_messages) == 1
                req_msg = request.request_messages[0]
                request_payload = UnaryRequest()

                assert req_msg.Is(request_payload.DESCRIPTOR)
                req_msg.Unpack(request_payload)

                unary_response = client.call_unary(
                    request_payload,
                    extra_headers=extra_headers,
                    timeout_seconds=timeout_seconds,
                )
                result = result_from_unary_output(unary_response)
                response.response.MergeFrom(result)

            elif request.method == "ServerStream":
                assert len(request.request_messages) == 1
                req_msg = request.request_messages[0]
                request_payload = ServerStreamRequest()
                assert req_msg.Is(request_payload.DESCRIPTOR)
                req_msg.Unpack(request_payload)

                server_stream_output = client.call_server_stream(
                    request_payload,
                    extra_headers=extra_headers,
                    timeout_seconds=timeout_seconds,
                )
                result = result_from_stream_output(server_stream_output)
                response.response.MergeFrom(result)

            elif request.method == "ClientStream":

                def client_stream_requests() -> Generator[ClientStreamRequest]:
                    for msg in request.request_messages:
                        req_payload = ClientStreamRequest()
                        msg.Unpack(req_payload)
                        time.sleep(request.request_delay_ms / 1000.0)
                        yield req_payload

                client_stream_output = client.call_client_stream(
                    client_stream_requests(),
                    extra_headers=extra_headers,
                    timeout_seconds=timeout_seconds,
                )
                result = result_from_unary_output(client_stream_output)
                response.response.MergeFrom(result)

            elif request.method == "BidiStream":

                def client_bidi_requests() -> Generator[BidiStreamRequest]:
                    for msg in request.request_messages:
                        req_payload = BidiStreamRequest()
                        msg.Unpack(req_payload)
                        time.sleep(request.request_delay_ms / 1000.0)
                        yield req_payload

                bidi_stream_output = client.call_bidi_stream(
                    client_bidi_requests(),
                    extra_headers=extra_headers,
                    timeout_seconds=timeout_seconds,
                )
                result = result_from_stream_output(bidi_stream_output)
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
                unimplemented_response = client.call_unimplemented(
                    request_payload,
                    extra_headers=extra_headers,
                    timeout_seconds=timeout_seconds,
                )
                result = result_from_unary_output(unimplemented_response)
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


async def handle_async(request: ClientCompatRequest) -> ClientCompatResponse:
    """Handle a ClientCompatRequest and return a blank ClientCompatResponse."""

    response = ClientCompatResponse()
    response.test_name = request.test_name
    debug("request: ", request)
    timeout_seconds: float | None = None
    if request.timeout_ms != 0:
        timeout_seconds = request.timeout_ms / 1000.0
    debug("request timeout: ", timeout_seconds)
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

            client = AsyncConformanceServiceClient(
                base_url="http://" + request.host + ":" + str(request.port),
                http_client=http_session,
                protocol=protocol,
            )

            extra_headers = request_headers(request)
            request_payload: (
                UnaryRequest
                | ServerStreamRequest
                | ClientStreamRequest
                | BidiStreamRequest
                | UnimplementedRequest
            )

            if request.method == "Unary":
                assert len(request.request_messages) == 1
                req_msg = request.request_messages[0]
                request_payload = UnaryRequest()

                assert req_msg.Is(request_payload.DESCRIPTOR)
                req_msg.Unpack(request_payload)

                response = ClientCompatResponse()
                response.test_name = request.test_name
                unary_response = await client.call_unary(
                    request_payload,
                    extra_headers=extra_headers,
                    timeout_seconds=timeout_seconds,
                )
                result = result_from_unary_output(unary_response)
                response.response.MergeFrom(result)

            elif request.method == "ServerStream":
                assert len(request.request_messages) == 1
                req_msg = request.request_messages[0]
                request_payload = ServerStreamRequest()
                assert req_msg.Is(request_payload.DESCRIPTOR)
                req_msg.Unpack(request_payload)

                server_stream_output = await client.call_server_stream(
                    request_payload,
                    extra_headers=extra_headers,
                    timeout_seconds=timeout_seconds,
                )
                result = await result_from_async_stream_output(server_stream_output)
                response.response.MergeFrom(result)

            elif request.method == "ClientStream":

                async def client_stream_requests() -> AsyncGenerator[ClientStreamRequest]:
                    for msg in request.request_messages:
                        req_payload = ClientStreamRequest()
                        msg.Unpack(req_payload)
                        await asyncio.sleep(request.request_delay_ms / 1000.0)
                        yield req_payload

                client_stream_output = await client.call_client_stream(
                    client_stream_requests(),
                    extra_headers=extra_headers,
                    timeout_seconds=timeout_seconds,
                )
                result = result_from_unary_output(client_stream_output)
                response.response.MergeFrom(result)

            elif request.method == "BidiStream":

                async def client_bidi_requests() -> AsyncGenerator[BidiStreamRequest]:
                    for msg in request.request_messages:
                        req_payload = BidiStreamRequest()
                        msg.Unpack(req_payload)
                        await asyncio.sleep(request.request_delay_ms / 1000.0)
                        yield req_payload

                bidi_stream_output = await client.call_bidi_stream(
                    client_bidi_requests(),
                    extra_headers=extra_headers,
                    timeout_seconds=timeout_seconds,
                )
                result = await result_from_async_stream_output(bidi_stream_output)
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
                unimplemented_response = await client.call_unimplemented(
                    request_payload,
                    extra_headers=extra_headers,
                    timeout_seconds=timeout_seconds,
                )
                result = result_from_unary_output(unimplemented_response)
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


def result_from_stream_output(stream_output: StreamOutput[Any]) -> ClientResponseResult:
    result = ClientResponseResult()
    for server_msg in stream_output:
        result.payloads.append(server_msg.payload)

    resp_headers = multidict_to_proto(stream_output.response_headers())
    result.response_headers.extend(resp_headers)

    resp_trailers = multidict_to_proto(stream_output.response_trailers())
    result.response_trailers.extend(resp_trailers)

    err = stream_output.error()
    if err is not None:
        result.error.CopyFrom(exception_to_proto(err))

    return result


async def result_from_async_stream_output(
    stream_output: AsyncStreamOutput[Any],
) -> ClientResponseResult:
    result = ClientResponseResult()
    async with stream_output as stream:
        async for server_msg in stream:
            result.payloads.append(server_msg.payload)

    resp_headers = multidict_to_proto(stream_output.response_headers())
    result.response_headers.extend(resp_headers)

    resp_trailers = multidict_to_proto(stream_output.response_trailers())
    result.response_trailers.extend(resp_trailers)

    err = stream_output.error()
    if err is not None:
        result.error.CopyFrom(exception_to_proto(err))

    return result


def result_from_unary_output(unary_output: UnaryOutput[Any]) -> ClientResponseResult:
    result = ClientResponseResult()
    err = unary_output.error()
    if err is not None:
        result.error.CopyFrom(exception_to_proto(err))
    msg = unary_output.message()
    if msg is not None:
        result.payloads.append(msg.payload)

    headers = unary_output.response_headers()
    if headers is not None:
        headers_proto = multidict_to_proto(headers)
        result.response_headers.extend(headers_proto)

    resp_trailers = unary_output.response_trailers()
    if resp_trailers is not None:
        resp_trailers_proto = multidict_to_proto(resp_trailers)
        result.response_trailers.extend(resp_trailers_proto)

    return result


def request_headers(req: ClientCompatRequest) -> MultiDict[str]:
    """Convert protobuf headers to CIMultiDict, preserving all values."""
    headers: MultiDict[str] = MultiDict()
    for h in req.request_headers:
        for value in h.value:  # Preserve ALL values, not just the first one
            headers.add(h.name, value)
    return headers


def main(mode: str) -> None:
    """Main loop that reads requests from stdin and writes responses to stdout."""
    if mode not in {"sync", "async"}:
        raise ValueError("mode must be sync or async")
    while True:
        try:
            message_bytes = read_size_delimited_message()
            if message_bytes is None:
                break  # EOF

            # Parse the request
            request = ClientCompatRequest()
            request.ParseFromString(message_bytes)

            # Handle the request
            if mode == "async":
                response = asyncio.run(handle_async(request))
            elif mode == "sync":
                response = handle_sync(request)
            else:
                raise NotImplementedError
            # Write the response
            response_bytes = response.SerializeToString()
            write_size_delimited_message(response_bytes)

        except Exception as e:
            sys.stderr.write(f"Error processing request: {e}\n")
            sys.stderr.flush()
            break


if __name__ == "__main__":
    main(sys.argv[1])
