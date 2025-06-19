# Connect Python

A Python implementation of the Connect RPC framework.

This provides an asynchronous client runtime, as well as a client code
generator, to let Python programs communicate with Connect servers.

## Features

 - Async `aiohttp`-powered implementation for efficient use in real
   production servers.
 - Fully type-annotated, including the generated code, and verified
   with mypy.
 - Verified implementation using the official
   [conformance](https://github.com/connectprc/conformance) test
   suite.

## Usage

With a protobuf definition in hand, you can generate a client. This is
easiest using buf, but you can also use protoc if you're feeling
masochistic.

Install the compiler (eg `pip install connect-python[compiler]`), and
it can be referenced as `protoc-gen-connect_python`.

A reasonable `buf.gen.yaml`:
```yaml
version: v2
plugins:
  - remote: buf.build/protocolbuffers/python
    out: .
  - remote: buf.build/protocolbuffers/pyi
    out: .
  - local: .venv/bin/protoc-gen-connect_python
    out: .
```

If you have a proto definition like this:

```proto
service ElizaService {
  rpc Say(SayRequest) returns (SayResponse) {}
  rpc Converse(stream ConverseRequest) returns (stream ConverseResponse) {}
  rpc Introduce(IntroduceRequest) returns (stream IntroduceResponse) {}
  rpc Pontificate(stream PontificateRequest) returns (PontificateResponse) {}
}
```

Then the generated client will have methods like this (optional arguments have been elided for clarity):
```python
class AsyncElizaServiceClient:
    def __init__(self, base_url: str, http_client: aiohttp.ClientSession):
        ...

    # Unary (no streams)
    async def say(self, req: eliza_pb2.SayRequest) -> eliza_pb2.SayResponse:
        ...
        
    # Bidirectional (both sides stream)
    def converse(self, req: StreamInput[eliza_pb2.ConverseRequest]) -> AsyncIterator[eliza_pb2.SayResponse]:
        ...
        
    # Server streaming (client sends one message, server sends a stream)
    def introduce(self, req: eliza_pb2.IntroduceRequest) -> AsyncIterator[eliza_pb2.IntroduceResponse]:
        ...
        
    # Client streaming (client sends a stream, server sends one message back)
    def pontificate(self, req: StreamInput[eliza_pb2.PontificateRequest]) -> eliza_pb2.PontificateResponse]:
        ...
```

which you can use like this:

```python
async def main():
    with aiohttp.ClientSession() as http_client:
        eliza_client = AsyncElizaServiceClient("https://demo.connectrpc.com")
        
        # Unary responses: await and get the response message back
        response = await eliza_client.say(eliza_pb2.SayRequest(sentence="Hello, Eliza!"))
        print(f"  Eliza says: {response.sentence}")
        
        # Streaming responses: use async for to iterate over messages in the stream
        req = eliza_pb2.IntroduceRequest(name="Henry")
        async for response in eliza_client.introduce(req):
            print(f"   Eliza: {response.sentence}")
            
        # Streaming requests: send an iterator, get a single message
        requests = [
            eliza_pb2.PontificateRequest(sentence="I have many things on my mind."),
            eliza_pb2.PontificateRequest(sentence="But I will save them for later."),
        ]
        response = await eliza_client.pontificate(requests)
        print("    Eliza responds: {response.sentence}")
            
        # Bidirectional RPCs: send an iterator, get an iterator
        requests = [
            eliza_pb2.ConverseRequest(sentence="I have been having trouble communicating."),
            eliza_pb2.ConverseRequest(sentence="But structured RPCs are pretty great!"),
            eliza_pb2.ConverseRequest(sentence="What do you think?")
        ]
        async for response in eliza_client.converse(requests):
            print("    Eliza: {response.sentence}")
        
```

### Advanced usage

#### Sending extra headers

All RPC methods take an `extra_headers: HeaderInput`
argument. `HeaderInput` is defined in
[connectrpc.headers](./src/connectrpc/headers.py), and is a type
alias; you can use a `dict[str, str]`.

So if you want to send a header like `X-Favorite-RPC: Connect` in your
`say` request, you'd do this:

```python
eliza_client.say(req, extra_headers={"X-Favorite-RPC": "Connect"})
```

#### Per-request timeouts

All RPC methods take a `timeout_seconds: float` argument. When passed,
the timeout will be used in two ways:

 1. It will be set in the `Connect-Timeout-Ms` header, so the server
    will be informed of the deadline you have set.
 2. `aiohttp` will be informed, and will close the request if the
    timeout expires.
    
So for example:
```python
eliza_client.say(req, timeout_seconds=2.5)
```

#### Low-level Call APIs

Connect supports response headers and trailers, and has a rich error
system. To get access to these, use the low-level `call` APIs.

Each generated RPC method has an associated `call_` method. For
example, the `say` RPC will have `eliza_client.call_say`, and the
`converse` RPC will have `eliza_client.call_converse`, and so on.

These `call` methods return types which represents the nitty-gritty
details, and can be used to access response header and trailer
metadata

 - for unary requests and client-streaming requests, the response `T`
   is wrapped in a `connectrpc.unary.UnaryOutput[T]`.
 - for server-streaming and bidirectional requests, you get
   `connectrpc.streams.StreamOutput[T]`.

##### Accessing messages

For `UnaryOutput`, the message is easy to get - it's under a `message()` accessor:

```python
output = await eliza_client.call_say(req)
response = output.message()
print(response.sentence)
```

`StreamOutput`s require a little more work. In order to avoid leaking
HTTP connection resources, StreamOutputs need to be cleaned up after
use with `output.close()`. You can handle that by using them as a
context manager:

```python
output = await eliza_client.call_introduce(req)
async with output as stream:
    ...  # All IO will happen inside this block
```

The stream from this context manager is an iterator - you can iterate
over the messages this way:

```python
messages = []
output = await eliza_client.call_introduce(req)
async with output as stream:
    async for response in stream:
        # each element in stream is the protobuf message type, 
        # already deserialized
        messages.append(response.sentence)
        
if output.error() is not None:
    raise output.error()
```

##### Response metadata

`UnaryOutput` and `StreamOutput` provide access to metadata in the same way:

```python
headers = output.response_headers() 
trailers = output.response_trailers()
```

These are
[`CIMultiDict[str]`](https://multidict.aio-libs.org/en/stable/multidict/#multidict.CIMultiDict)
objects - that is, case-insensitive multiple-valued
dictionaries. Basically, you can think of them as `dict[str,
list[str]]` with case-insensitive keys and a few conveniences.

Note that the `response_trailers` of a `StreamOutput` are only
accessible after the stream has been fully consumed. Iterate over all
responses in the stream before trying to access the trailers, or else
you'll get an exception.

##### Errors

`UnaryOutput` and `StreamOutput` both give you errors through the
`error()` accessor function, which returns a
`connectrpc.errors.ConnectError` exception, which includes a code,
message, and optionally extra details.

Note that the error in a `StreamOutput` might not be available until
you've consumed all messages in the stream. For `UnaryOutput`, it is
available right away.

The `call` APIs do not generally raise errors. It's up to you to
`raise output.error()` if you so desire.

## Current State

This is an early implementation which only covers the client side.

### Supported Features

The client supports the Connect Protocol over HTTP 1.1, verified with
the official conformance test suite.

Unary, client streaming, and server streaming RPCs are fully
supported.

Only half-duplex bidirectional streaming is supported. This means the
client sends _all_ of its stream messages before yielding any of the
server's responses. This is because we're on HTTP 1.1.

The client correctly handles response headers, trailers, and all error
codes.

### Not yet supported (but definitely planned)

- A simpler synchronous client generated alongside the async one
- Compression
- Conformance tests of TLS

### Not yet supported (and maybe never will be?)

- http/2 transport

## Installation

For basic client functionality:
```bash
pip install connect-python
```

For code generation (protoc plugin):
```bash
pip install connect-python[compiler]
```

### Development

We use `ruff` for linting and formatting, and `mypy` for type checking.

We rely on the conformance test suit (in
[./tests/conformance](./tests/conformance)) to verify behavior.

Set up development dependencies:
```sh
uv sync --extra dev --extra compiler
```

Install the package in editable mode to produce a local `protoc-gen-connect_python` plugin for use with `protoc`:
```sh
uv pip install -e .[compiler]
```

Then, use `uv run just` to do development checks:
```
Available recipes:
    all                    # Run all checks (format, check, mypy, test, integration-test)
    check                  # Check code with ruff linter
    conformance-test *ARGS # Run conformance tests (requires connectconformance binary). Usage: just conformance-test [ARGS...]
    fix                    # Fix auto-fixable ruff linter issues
    format                 # Format code with ruff
    integration-test       # Run integration test against demo.connectrpc.com
    mypy                   # Run mypy type checking
    mypy-package
    mypy-tests
    protoc-gen *ARGS       # Run protoc with connect_python plugin (development mode). usage: just protoc-gen [PROTOC_ARGS...]
    test                   # Run tests
```

For example, `uv run check` will lint code.
