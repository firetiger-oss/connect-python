import struct
import sys

from connectrpc.conformance.v1.client_compat_pb2 import ClientCompatRequest
from connectrpc.conformance.v1.client_compat_pb2 import ClientCompatResponse


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


def handle(request: ClientCompatRequest) -> ClientCompatResponse:
    """Handle a ClientCompatRequest and return a blank ClientCompatResponse."""
    response = ClientCompatResponse()
    response.test_name = request.test_name
    return response


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
            response = handle(request)

            # Write the response
            response_bytes = response.SerializeToString()
            write_size_delimited_message(response_bytes)

        except Exception as e:
            sys.stderr.write(f"Error processing request: {e}\n")
            sys.stderr.flush()
            break


if __name__ == "__main__":
    main()
