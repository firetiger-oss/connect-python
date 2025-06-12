# Connect Python Client API Design - Lessons Learned

## Key Design Patterns Established

### Client API Architecture
- **Protocol-based design**: `BaseClient` protocol with concrete implementations
- **Facade pattern**: `ConnectClient` delegates to protocol-specific implementations
- **Method-level generics**: Each call specifies its own response type vs class-level generics
- **Duck typing for streams**: `StreamInput = Union[AsyncIterator[T], Iterable[T]]` allows lists, generators, async iterators

### Critical Type System Fix: async def vs def for AsyncIterator Returns
**Problem**: `async def call_server_streaming() -> AsyncIterator[T]` creates `Awaitable[AsyncIterator[T]]`, but `async for` expects `AsyncIterator[T]` directly.

**Solution**: Use `def` (not `async def`) for methods returning `AsyncIterator[T]`:
```python
# WRONG: async def -> requires await before async for
async def call_server_streaming(...) -> AsyncIterator[T]: ...

# CORRECT: def -> direct async for usage  
def call_server_streaming(...) -> AsyncIterator[T]: ...
```

**Rule**: If users iterate with `async for`, method should return `AsyncIterator[T]` directly.

### Integration Testing Pattern
- **Service wrapper**: `ElizaServiceClient` wraps generic `ConnectClient` with typed methods
- **CLI protocol selection**: `--protocols connect-proto connect-json grpc grpc-web`
- **Comprehensive RPC coverage**: Unary, server streaming, bidirectional streaming
- **Real service testing**: Uses https://demo.connectrpc.com/

### Usage Patterns Enabled
```python
# Unary
response = await client.call_unary(url, request, ResponseType)

# Server streaming - direct async for
async for response in client.call_server_streaming(url, request, ResponseType):
    process(response)

# Client streaming with flexible input types
response = await client.call_client_streaming(url, [req1, req2], ResponseType)
response = await client.call_client_streaming(url, generator(), ResponseType)
```

### Implementation Status
- Integration test framework: ✅ Complete
- Type system: ✅ Fixed
- Protocol clients: ❌ Stubs (`NotImplementedError`)

**Next**: Implement actual protocol clients (ConnectProtobuf, ConnectJSON, gRPC, gRPC-Web)
