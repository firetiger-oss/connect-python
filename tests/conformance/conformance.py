import struct
import sys


def read_size_delimited_message() -> bytes | None:
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


def write_size_delimited_message(message_bytes: bytes) -> None:
    """Write a size-delimited protobuf message to stdout."""
    # Write 4-byte big-endian length prefix
    length = len(message_bytes)
    sys.stdout.buffer.write(struct.pack(">I", length))

    # Write the actual message
    sys.stdout.buffer.write(message_bytes)
    sys.stdout.buffer.flush()
