# Connect Python Client API Design - Lessons Learned

## Key Design Patterns Established

### Client API Architecture
- **Protocol-based design**: `BaseClient` protocol with concrete implementations
- **Facade pattern**: `ConnectClient` delegates to protocol-specific implementations
- **Method-level generics**: Each call specifies its own response type vs class-level generics
- **Duck typing for streams**: `StreamInput = Union[AsyncIterator[T], Iterable[T]]` allows lists, generators, async iterators

### Type System Evolution: From def to async def for Protocol Methods
**Original Design (Deprecated)**: `def call_streaming() -> StreamOutput[T]` for direct `async for` usage without await.

**Problem Discovered**: HTTP streaming requires async connection setup, but protocol expected synchronous stream object return.

**Solution (Dec 2024)**: Make protocol methods async to properly handle connection lifecycle:
```python
# CURRENT: async def enables proper connection setup
async def call_streaming(...) -> StreamOutput[T]: ...

# Usage pattern now requires await:
stream = await client.call_server_streaming(url, request, ResponseType)
async for response in stream:
    process(response)
```

**Key Insight**: Being honest about async nature of connection establishment improves resource management.

### Integration Testing Pattern
- **Service wrapper**: `ElizaServiceClient` wraps generic `ConnectClient` with typed methods
- **CLI protocol selection**: `--protocols connect-proto connect-json grpc grpc-web`
- **Comprehensive RPC coverage**: Unary, server streaming, bidirectional streaming
- **Real service testing**: Uses https://demo.connectrpc.com/

### Usage Patterns Enabled
```python
# Unary
response = await client.call_unary(url, request, ResponseType)

# Server streaming - now requires await
stream = await client.call_server_streaming(url, request, ResponseType)
async for response in stream:
    process(response)

# Client streaming with flexible input types
response = await client.call_client_streaming(url, [req1, req2], ResponseType)
response = await client.call_client_streaming(url, generator(), ResponseType)
```

### Simplified Protocol Interface (Dec 2024)
**Key Insight**: Protocol implementations only need `call_streaming` + `call_unary`. All streaming variants are just different ways to call these primitives.

**Architecture Decision**: 
- `BaseClient` protocol: Only `async call_unary()` and `async call_streaming()` 
- `ConnectClient`: Implements streaming variants by calling protocol methods:
  - `call_client_streaming()` → `await call_streaming()` + return first response
  - `call_server_streaming()` → wrap single request + `await call_streaming()`  
  - `call_bidirectional_streaming()` → direct `await call_streaming()`

**Benefits**:
- Simpler protocol implementations (less duplication)
- Consistent streaming variant logic across all protocols
- Protocol authors focus on core streaming mechanics
- Proper async connection lifecycle management

### StreamOutput API (Dec 2024)
**Key Innovation**: Rich streaming return type with trailing metadata access.

**Problem**: Original `AsyncIterator[T]` return type couldn't expose trailing metadata from Connect protocol `EndStreamResponse`.

**Solution**: `StreamOutput[T]` protocol with resource management and metadata access:
```python
# Context manager usage (recommended)
async with await client.call_server_streaming(url, request, ResponseType) as stream:
    async for response in stream:
        process(response)
# Connection automatically released

# Manual cleanup  
stream = await client.call_server_streaming(url, request, ResponseType)
try:
    async for response in stream:
        process(response)
finally:
    await stream.done()  # Explicit connection cleanup

# Access trailing metadata after consumption
metadata = stream.trailing_metadata()  # Returns Optional[dict], raises if not consumed
```

**Architecture**:
- `StreamOutput[T]`: Protocol with `__aiter__()`, `trailing_metadata()`, `done()`, and async context manager support
- `BaseClient.call_streaming()`: Returns `StreamOutput[T]` with proper connection lifecycle
- `ConnectProtobufClient`: Captures metadata from `EndStreamResponse` and manages HTTP connection pooling
- Connection lifecycle: Automatically releases on completion, early termination, or exceptions

**Benefits**:
- ✅ Proper resource management: HTTP connections returned to pool via `release()`
- ✅ Simple metadata access: Synchronous `trailing_metadata()` method  
- ✅ Flexible cleanup: Both context manager and explicit `done()` patterns
- ✅ Exception safety: Connections released even on errors
- ✅ Protocol agnostic: Works for all Connect, gRPC, gRPC-Web protocols

### Implementation Status
- Integration test framework: ✅ Complete
- Type system: ✅ Fixed (async protocol methods)
- Protocol interface: ✅ Simplified (2 async methods)
- ConnectProtobuf client: ✅ Complete with connection pooling
- StreamOutput API: ✅ Complete with resource management (Dec 2024)
- Connection lifecycle: ✅ Fixed (release vs close, context managers, exception safety)
- Other protocol clients: ❌ Stubs (`NotImplementedError`)

### Resource Management Lessons Learned (Dec 2024)
**Critical Fix**: Connection lifecycle management for streaming responses.

**Problem**: HTTP connections were being closed prematurely with `async with` context manager, causing "Connection closed" errors during stream consumption.

**Solution**: 
- Pass full `ClientResponse` to `StreamOutput` implementation
- Use `await resp.release()` instead of `await resp.close()` for connection pooling
- Implement async context manager protocol for automatic cleanup
- Add explicit `done()` method for manual resource management
- Release connections on normal completion, early termination, and exceptions

**Key Insight**: aiohttp connection lifecycle requires careful management - `release()` returns connections to pool while `close()` terminates them entirely.

**Next**: Implement actual protocol clients (ConnectJSON, gRPC, gRPC-Web)

# Development Commands
## Testing
- `just test` - Run pytest unit tests
- `just integration-test` - Run integration test against demo.connectrpc.com (connect-proto only)
- `just integration-test-all` - Run integration test with all protocols
- `just all` - Run all checks including integration tests

## Other Commands
- `just format` - Format code with ruff
- `just check` - Lint with ruff  
- `just mypy` - Type checking
