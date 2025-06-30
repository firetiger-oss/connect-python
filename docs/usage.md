# Usage Guide

## Basic Client Usage

### Synchronous Client

```python
import urllib3
from your_generated_code import ElizaServiceClient, eliza_pb2

# Create client
eliza_client = ElizaServiceClient("https://demo.connectrpc.com", urllib3.PoolManager())

# Unary responses:
response = eliza_client.say(eliza_pb2.SayRequest(sentence="Hello, Eliza!"))
print(f"  Eliza says: {response.sentence}")

# Streaming responses: use 'for' to iterate over messages in the stream
req = eliza_pb2.IntroduceRequest(name="Henry")
for response in eliza_client.introduce(req):
    print(f"   Eliza: {response.sentence}")

# Streaming requests: send an iterator, get a single message
requests = [
    eliza_pb2.PontificateRequest(sentence="I have many things on my mind."),
    eliza_pb2.PontificateRequest(sentence="But I will save them for later."),
]
response = eliza_client.pontificate(requests)
print(f"    Eliza responds: {response.sentence}")

# Bidirectional RPCs: send an iterator, get an iterator.
requests = [
    eliza_pb2.ConverseRequest(sentence="I have been having trouble communicating."),
    eliza_pb2.ConverseRequest(sentence="But structured RPCs are pretty great!"),
    eliza_pb2.ConverseRequest(sentence="What do you think?")
]
for response in eliza_client.converse(requests):
    print(f"    Eliza: {response.sentence}")
```

### Asynchronous Client

The code generator also produces an async client for concurrent operations:

```python
import aiohttp
from your_generated_code import AsyncElizaServiceClient, eliza_pb2

async def main():
    async with aiohttp.ClientSession() as http_client:
        eliza_client = AsyncElizaServiceClient("https://demo.connectrpc.com", http_client)

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
        print(f"    Eliza responds: {response.sentence}")

        # Bidirectional RPCs: send an iterator, get an iterator
        requests = [
            eliza_pb2.ConverseRequest(sentence="I have been having trouble communicating."),
            eliza_pb2.ConverseRequest(sentence="But structured RPCs are pretty great!"),
            eliza_pb2.ConverseRequest(sentence="What do you think?")
        ]
        async for response in eliza_client.converse(requests):
            print(f"    Eliza: {response.sentence}")
```

## Advanced Usage

### Sending Extra Headers

All RPC methods take an `extra_headers: HeaderInput` argument. `HeaderInput` is defined in
`connectrpc.headers`, and is a type alias; you can use a `dict[str, str]`.

```python
eliza_client.say(req, extra_headers={"X-Favorite-RPC": "Connect"})
```

### Per-request Timeouts

All RPC methods take a `timeout_seconds: float` argument:

```python
eliza_client.say(req, timeout_seconds=2.5)
```

The timeout will be used in two ways:
1. It will be set in the `Connect-Timeout-Ms` header, so the server will be informed of the deadline
2. The HTTP client will be informed, and will close the request if the timeout expires

### Low-level Call APIs

For access to response headers, trailers, and rich error information, use the low-level `call` APIs.

Each generated RPC method has an associated `call_` method. For example, the `say` RPC will have `eliza_client.call_say`.

#### Unary Calls

```python
output = eliza_client.call_say(req)
response = output.message()
headers = output.response_headers()
trailers = output.response_trailers()

if output.error() is not None:
    raise output.error()
```

#### Streaming Calls

```python
output = eliza_client.call_introduce(req)
with output as stream:
    for response in stream:
        print(response.sentence)

if output.error() is not None:
    raise output.error()
```

#### Async Streaming Calls

```python
output = async_eliza_client.call_introduce(req)
async with output as stream:
    async for response in stream:
        print(response.sentence)

if output.error() is not None:
    raise output.error()
```

## Server Implementation

### WSGI Server

The generated code includes a function to mount an object implementing your service as a WSGI application:

```python
def wsgi_eliza_service(implementation: ElizaServiceProtocol) -> WSGIApplication:
    ...
```

Your implementation needs to follow the `ElizaServiceProtocol`:

```python
from connectrpc.server import ClientRequest, ClientStream, ServerResponse, ServerStream

class ElizaServiceImpl:
    def say(self, req: ClientRequest[eliza_pb2.SayRequest]) -> ServerResponse[eliza_pb2.SayResponse]:
        response = eliza_pb2.SayResponse(sentence=f"You said: {req.msg.sentence}")
        return ServerResponse(response)
    
    def converse(self, req: ClientStream[eliza_pb2.ConverseRequest]) -> ServerStream[eliza_pb2.ConverseResponse]:
        def generate_responses():
            for msg in req:
                yield eliza_pb2.ConverseResponse(sentence=f"You said: {msg.sentence}")
        
        return ServerStream(generate_responses())
```

## Current Limitations

### Client

- Only half-duplex bidirectional streaming is supported (HTTP 1.1 limitation)
- Client compression is not yet supported
- HTTP/2 transport is not supported

### Server

- Only WSGI-based servers are currently supported
- ASGI support is planned but not yet implemented
- Only half-duplex bidirectional streaming is supported