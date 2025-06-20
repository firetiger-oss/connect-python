import sys

from conformance import read_size_delimited_message
from conformance import write_size_delimited_message
from connectrpc.conformance.v1.server_compat_pb2 import ServerCompatRequest
from connectrpc.conformance.v1.server_compat_pb2 import ServerCompatResponse


def handle_sync(req: ServerCompatRequest) -> ServerCompatResponse:
    raise NotImplementedError


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
            request = ServerCompatRequest()
            request.ParseFromString(message_bytes)

            # Handle the request
            if mode == "async":
                raise NotImplementedError
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
