# Examples

This section contains practical examples of using connect-python.

## Basic Client Example

Here's a simple synchronous client example:

```python
import urllib3
from your_generated_code import ElizaServiceClient, eliza_pb2

# Create client
eliza_client = ElizaServiceClient("https://demo.connectrpc.com", urllib3.PoolManager())

# Make a simple unary call
response = eliza_client.say(eliza_pb2.SayRequest(sentence="Hello, Eliza!"))
print(f"Eliza says: {response.sentence}")
```

## Async Client Example

For asynchronous operations:

```python
import aiohttp
from your_generated_code import AsyncElizaServiceClient, eliza_pb2

async def main():
    async with aiohttp.ClientSession() as http_client:
        eliza_client = AsyncElizaServiceClient("https://demo.connectrpc.com", http_client)
        
        # Make an async unary call
        response = await eliza_client.say(eliza_pb2.SayRequest(sentence="Hello, Eliza!"))
        print(f"Eliza says: {response.sentence}")
```

## More Examples

For more detailed examples, see the [Usage Guide](../usage.md).