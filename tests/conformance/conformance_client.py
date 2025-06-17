import asyncio
import aiohttp
import struct
import sys
import traceback

from connectrpc.client import ConnectProtocol

from connectrpc.conformance.v1.config_pb2 import Protocol
from connectrpc.conformance.v1.config_pb2 import Codec
from connectrpc.conformance.v1.client_compat_pb2 import ClientCompatRequest
from connectrpc.conformance.v1.client_compat_pb2 import ClientCompatResponse
from connectrpc.conformance.v1.client_compat_pb2 import ClientErrorResult
from connectrpc.conformance.v1.service_pb2_connect import ConformanceServiceClient
from connectrpc.conformance.v1.service_pb2 import UnaryRequest


async def handle(request: ClientCompatRequest) -> ClientCompatResponse:
    """Handle a ClientCompatRequest and return a blank ClientCompatResponse."""

    response = ClientCompatResponse()
    response.test_name = request.test_name
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

            if request.method == "Unary":
                assert len(request.request_messages) == 1
                req_msg = request.request_messages[0]
                request_payload = UnaryRequest()
                assert req_msg.Is(request_payload.DESCRIPTOR)
                req_msg.Unpack(request_payload)
                server_response = await client.unary(request_payload)
            else:
                raise NotImplementedError

        return response
    except Exception as e:
        response.error.CopyFrom(ClientErrorResult(message=traceback.format_exc()))
        return response


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
