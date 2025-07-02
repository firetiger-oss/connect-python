# ConnectRPC ASGI Implementation Tasks

This document outlines the complete task breakdown for implementing ASGI support in ConnectRPC Python. Each task is designed to be completed in a separate Claude session with clear deliverables and success criteria.

## Overview

The goal is to implement a complete ASGI server for the Connect protocol, supporting all RPC types (unary, client streaming, server streaming, bidirectional streaming) with true full-duplex capabilities that surpass the current WSGI implementation.

### Architecture Summary

```
ASGI Server → ConnectASGI → Connect Protocol Processing → User Handlers
              ↓
         [Unary, Client Stream, Server Stream, Bidi Stream]
```

### Key Design Decisions

1. **Single Handler API**: All streaming uses `AsyncIterator[T]` return type for consistency
2. **True Full-Duplex**: ASGI enables concurrent read/write, unlike current WSGI half-duplex limitation
3. **Protocol Reuse**: Existing domain types (`ClientRequest`, `ServerResponse`) remain unchanged
4. **Incremental Implementation**: Build from unary RPCs up to full streaming support
5. **Early Conformance Testing**: Run conformance tests as features are implemented, starting with unary-only configuration

---

## Phase 1: Foundation

### Task 1: ASGI Event Primitives - Request Body Reader

**Description**: Create an async request body reader that properly handles ASGI's event-driven request model.

**Context**: Unlike WSGI where the request body is available as a file-like object, ASGI delivers request bodies through multiple `http.request` events that must be accumulated until `more_body=False`.

**Deliverables**:
- `AsyncRequestBodyReader` class in new file `src/connectrpc/server_asgi_io.py`
- Handles incremental `http.request` events via ASGI `receive` callable
- Provides both `read_all()` and `read_exactly(n)` methods
- Proper error handling for malformed or incomplete requests
- Raw byte reading only (compression handled at higher levels: unary in Task 6, streaming in Task 4)

**Success Criteria ("Done")**:
- Unit tests pass for various request body scenarios:
  - Single event with complete body (`more_body=False`)
  - Multiple events with partial bodies (`more_body=True` → `more_body=False`)
  - Empty request bodies
  - Large request bodies (>64KB) split across many events
  - Connection disconnect during body reading
- Integration test: Can read request bodies from real ASGI server (uvicorn)

**Files to Create/Modify**:
- `src/connectrpc/server_asgi_io.py` (new)
- Tests: `tests/test_asgi_io.py` (new)

---

### Task 2: ASGI Event Primitives - Response Sender

**Description**: Create an async response sender that properly implements ASGI's response protocol.

**Context**: ASGI responses require sending `http.response.start` event followed by one or more `http.response.body` events. The sender must handle the ASGI protocol correctly and efficiently.

**Deliverables**:
- `AsyncResponseSender` class in `src/connectrpc/server_asgi_io.py`
- `send_start(status, headers, trailers=False)` method for `http.response.start`
- `send_body(data, more_body=True)` method for `http.response.body` events
- `send_complete(data=b"")` convenience method for final body chunk
- Proper error handling for closed connections and ASGI protocol violations
- Support for HTTP trailers (set `trailers=True` in start, send via final body event)

**Success Criteria ("Done")**:
- Unit tests pass for response sending scenarios:
  - Simple response (start + single body with `more_body=False`)
  - Streaming response (start + multiple body chunks)
  - Empty response body
  - Response with HTTP trailers
  - Error handling when connection is closed
- Integration test: Can send responses through real ASGI server
- Performance test: Efficiently handles large response bodies without excessive memory usage

**Files to Create/Modify**:
- `src/connectrpc/server_asgi_io.py` (extend)
- Tests: `tests/test_asgi_io.py` (extend)

---

### Task 3: ASGI Event Primitives - Scope Wrapper

**Description**: Create an ASGI scope wrapper that extracts HTTP connection metadata in a format compatible with existing Connect protocol processing.

**Context**: ASGI provides request metadata in the `scope` dict. We need to extract and normalize this data (headers, path, method, etc.) for use by Connect protocol handlers, similar to how `WSGIRequest` works.

**Deliverables**:
- `ASGIScope` class in `src/connectrpc/server_asgi_io.py`
- Properties for accessing: `method`, `path`, `query_string`, `headers`, `content_type`
- Header normalization (ASGI headers are `[[bytes, bytes], ...]` format)
- Compatibility layer matching `WSGIRequest` interface where possible
- Proper handling of edge cases (missing headers, malformed paths, etc.)

**Success Criteria ("Done")**:
- Unit tests pass for scope parsing scenarios:
  - Standard HTTP request scopes (GET, POST with various headers)
  - Edge cases: missing Content-Type, duplicate headers, empty paths
  - Header case normalization (ASGI headers should be lowercase)
  - Query string handling and URL decoding
- Integration test: Scope wrapper correctly extracts metadata from real ASGI requests
- Compatibility test: Existing Connect protocol validation works with `ASGIScope`

**Files to Create/Modify**:
- `src/connectrpc/server_asgi_io.py` (extend)
- Tests: `tests/test_asgi_io.py` (extend)

---

### Task 4: Connect Protocol Async I/O - Envelope Parser

**Description**: Create an async envelope parser for Connect protocol's streaming message format.

**Context**: Connect streaming uses length-delimited envelopes: `[1 byte flags][4 bytes big-endian length][data]`. The current sync implementation uses `struct.unpack` on blocking I/O. We need an async version that works with ASGI receive events.

**Deliverables**:
- `AsyncEnvelopeParser` class in new file `src/connectrpc/connect_async_io.py`
- `parse_envelope(receive)` method that reads envelope header and message data
- Handles envelope flags: compression (0x01), end-stream (0x02)
- Integration with existing compression codecs
- Proper error handling for malformed envelopes or connection issues

**Success Criteria ("Done")**:
- Unit tests pass for envelope parsing scenarios:
  - Standard message envelopes (uncompressed and compressed)
  - End-stream envelopes with `EndStreamResponse` payload
  - Malformed envelopes (invalid length, truncated data)
  - Empty envelopes and zero-length messages
- Integration test: Can parse envelopes from real Connect streaming clients
- Performance test: Efficiently handles large messages without excessive memory allocation

**Files to Create/Modify**:
- `src/connectrpc/connect_async_io.py` (new)
- Tests: `tests/test_connect_async_io.py` (new)

---

### Task 5: Connect Protocol Async I/O - StreamReader Adaptation (**SKIPPED**)

**Status**: **SKIPPED** - Redundant with existing `AsyncRequestBodyReader`

**Reason**: The `AsyncRequestBodyReader` class (Task 1) already provides the needed functionality:
- Handles ASGI receive events with `read_exactly(n)` and `read_all()` methods  
- Proper EOF handling and connection lifecycle management
- Integration ready for Connect protocol processing

Creating an additional `AsyncStreamReader` layer would be redundant abstraction. Later tasks should use `AsyncRequestBodyReader` directly instead of referencing a non-existent `AsyncStreamReader`.

**Impact on Later Tasks**: References to `AsyncStreamReader` in subsequent tasks should be replaced with `AsyncRequestBodyReader`.

---

## Phase 2: Unary RPC Implementation

### Task 6: Unary RPC - AsyncConnectUnaryRequest

**Description**: Create an async version of `ConnectUnaryRequest` that reads complete request bodies from ASGI receive events.

**Context**: The current `ConnectUnaryRequest` (`src/connectrpc/server_requests.py`) reads from WSGI environ. We need an async version that uses the ASGI I/O primitives from Phase 1 while maintaining the same validation and processing logic.

**Deliverables**:
- `AsyncConnectUnaryRequest` class in new file `src/connectrpc/server_asgi_requests.py`
- `from_asgi(scope, receive, send)` class method for construction
- Async request body reading using `AsyncRequestBodyReader`
- Maintains existing validation logic (content-type, compression, headers)
- Handles decompression of complete request body (after reading, before deserialization)
- Compatibility with existing serialization and compression systems

**Success Criteria ("Done")**:
- Unit tests pass for unary request processing:
  - JSON and protobuf content types (`application/json`, `application/proto`)
  - Compressed and uncompressed request bodies
  - Proper header extraction and validation
  - Error handling for malformed requests
- Integration test: Can process real Connect unary requests from ASGI clients
- Compatibility test: Existing unary RPC handlers work with `AsyncConnectUnaryRequest`

**Files to Create/Modify**:
- `src/connectrpc/server_asgi_requests.py` (new)
- Tests: `tests/test_asgi_requests.py` (new)

---

### Task 7: Unary RPC - Request Validation

**Description**: Implement unary request validation for ASGI, adapting the existing validation framework.

**Context**: The current validation logic in `ConnectUnaryRequest` handles content-type negotiation, compression detection, and protocol compliance. This logic needs to be adapted for the ASGI event model while maintaining full compatibility.

**Deliverables**:
- Validation methods integrated into `AsyncConnectUnaryRequest`
- Content-type validation for unary protocols (`application/json`, `application/proto`)
- Compression handling (`content-encoding` header)
- Connect protocol compliance validation
- Error response generation compatible with ASGI response sending

**Success Criteria ("Done")**:
- Unit tests pass for validation scenarios:
  - Valid unary requests (JSON and protobuf, compressed and uncompressed)
  - Invalid content types and malformed requests
  - Missing required headers and protocol violations
  - Proper error response generation
- Integration test: Validation errors are properly sent as ASGI responses
- Conformance test: Validation behavior matches existing WSGI implementation

**Files to Create/Modify**:
- `src/connectrpc/server_asgi_requests.py` (extend)
- Tests: `tests/test_asgi_requests.py` (extend)

---

### Task 8: Unary RPC - Response Sending

**Description**: Implement unary response sending through ASGI events with proper headers, trailers, and error handling.

**Context**: Unary responses in Connect protocol include status codes, headers, trailers, and response bodies. The implementation must properly serialize responses and send them via ASGI events while handling both success and error cases.

**Deliverables**:
- Response sending logic integrated into `AsyncConnectUnaryRequest`
- Support for success responses with proper serialization
- Error response handling (Connect errors as HTTP 4xx/5xx with JSON bodies)
- Header and trailer management
- Integration with compression and serialization systems

**Success Criteria ("Done")**:
- Unit tests pass for response sending scenarios:
  - Successful unary responses (JSON and protobuf, compressed and uncompressed)
  - Error responses with proper Connect error format
  - Response headers and trailers
  - Various HTTP status codes and error conditions
- Integration test: Responses are properly received by Connect clients
- Compatibility test: Response format matches existing WSGI implementation

**Files to Create/Modify**:
- `src/connectrpc/server_asgi_requests.py` (extend)
- Tests: `tests/test_asgi_requests.py` (extend)

---

### Task 9: ConnectASGI Main Class - Core Implementation

**Description**: Create the main `ConnectASGI` class that implements the ASGI application interface.

**Context**: This is the central ASGI application class, similar to `ConnectWSGI` but designed for ASGI's async, event-driven model. It needs to implement the standard ASGI app signature: `async def app(scope, receive, send)`.

**Deliverables**:
- `ConnectASGI` class in new file `src/connectrpc/server_asgi.py`  
- ASGI app signature: `async def __call__(self, scope, receive, send)`
- RPC registration methods: `register_unary()`, etc.
- Basic routing based on HTTP method and path
- Connection type detection (HTTP vs WebSocket - reject WebSocket)
- Integration with request processing from Tasks 6-8
- Do NOT attempt to fully implement the routing layer or RPC calls, just the
  basic infrastructure of RPC registration and lookup.

**Success Criteria ("Done")**:
- Unit tests pass for core functionality:
  - ASGI app interface compliance
  - HTTP connection handling (reject WebSocket connections)
  - RPC registration and lookup
- Integration test: Can be deployed with real ASGI servers (uvicorn, hypercorn)
- Smoke test: Simple unary RPC works end-to-end

**Files to Create/Modify**:
- `src/connectrpc/server_asgi.py` (new)
- Tests: `tests/test_server_asgi.py` (new)

---

### Task 9.5: ASGI Conformance Testing Infrastructure

**Description**: Create ASGI conformance testing infrastructure based on the existing WSGI implementation, with unary-only configuration for early validation.

**Context**: The existing conformance tests (`tests/conformance/`) provide comprehensive Connect protocol validation using YAML configuration files that specify supported features. We need an ASGI version that initially supports only unary RPCs, allowing incremental testing as streaming features are implemented. This follows the same pattern as the WSGI `conformance_server.py` but uses the new ASGI implementation.

**Deliverables**:
- `conformance_server_asgi.py` in `tests/conformance/`
- ASGI conformance service implementation using `ConnectASGI`
- `asgi_unary_config.yaml` - Initial config supporting only unary RPCs with basic features:
  - `STREAM_TYPE_UNARY` only
  - `PROTOCOL_CONNECT` only  
  - `CODEC_PROTO` and `CODEC_JSON`
  - `COMPRESSION_IDENTITY` only (no gzip/brotli initially)
  - No HTTP/2, no trailers, no timeouts initially
- Integration with uvicorn/hypercorn for ASGI server lifecycle
- Command-line interface matching existing conformance server pattern
- Proper error handling and logging for conformance test debugging

**Success Criteria ("Done")**:
- ASGI conformance server can be started and responds to basic health checks
- Unary RPC conformance tests pass with the basic `ConnectASGI` implementation from Task 9
- Configuration system allows incremental enabling of features (compression, streaming types, etc.)
- Server lifecycle (startup/shutdown) works correctly with ASGI servers
- Integration test: Can run against existing conformance test runner
- Debugging: Clear error messages when tests fail due to unimplemented features

**Files to Create/Modify**:
- `tests/conformance/conformance_server_asgi.py` (new)
- `tests/conformance/asgi_unary_config.yaml` (new)  
- `tests/conformance/conftest.py` (extend with ASGI fixtures if needed)

**Dependencies**: Requires completion of Tasks 1-9 (basic unary ASGI implementation)

---

### Task 10: ConnectASGI Main Class - Unary RPC Routing

**Description**: Implement unary RPC routing and handler dispatch within the ASGI event loop.

**Context**: The routing system must match incoming requests to registered RPC handlers based on path and method, then execute the handler asynchronously while managing the complete request/response lifecycle.

**Deliverables**:
- Complete unary RPC handling pipeline in `ConnectASGI`
- Path-based routing (e.g., `/eliza.v1.ElizaService/Say`)
- Method validation (unary RPCs must be POST)
- Handler execution with proper async context management
- Integration of request processing, handler execution, and response sending

**Success Criteria ("Done")**:
- Unit tests pass for routing scenarios:
  - Successful unary RPC dispatch and execution
  - 404 handling for unknown paths
  - 405 handling for wrong HTTP methods
  - Handler exception propagation and error responses
- Integration test: Multiple unary RPCs can be registered and work correctly
- Performance test: Handler execution is properly async (doesn't block event loop)
- **Conformance test: Basic unary conformance tests pass with `asgi_unary_config.yaml`**

**Files to Create/Modify**:
- `src/connectrpc/server_asgi.py` (extend)
- Tests: `tests/test_server_asgi.py` (extend)

---

### Task 11: ConnectASGI Main Class - Connection Lifecycle

**Description**: Handle ASGI connection lifecycle and error scenarios properly.

**Context**: ASGI applications must handle connection events like disconnects, errors, and timeouts. The implementation needs robust error handling and proper resource cleanup.

**Deliverables**:
- Connection lifecycle management in `ConnectASGI`
- Proper handling of `http.disconnect` events
- Error handling for connection failures and timeouts
- Resource cleanup and graceful degradation
- Comprehensive logging and error reporting

**Success Criteria ("Done")**:
- Unit tests pass for error scenarios:
  - Client disconnect during request processing
  - Handler exceptions and error propagation
  - Connection timeouts and resource cleanup
  - ASGI protocol violations and recovery
- Integration test: Server remains stable under error conditions
- Load test: Server handles connection errors gracefully under load
- **Conformance test: Complete unary conformance test suite passes (expand `asgi_unary_config.yaml` to include compression, error handling)**

**Files to Create/Modify**:
- `src/connectrpc/server_asgi.py` (extend)
- Tests: `tests/test_server_asgi.py` (extend)

---

## Phase 3: Streaming RPC Implementation

### Task 12: Streaming Foundation - AsyncClientStream

**Description**: Create `AsyncClientStream[T]` that yields messages from ASGI receive events using the envelope parser.

**Context**: This is the async equivalent of `ClientStream[T]` that users interact with in streaming RPC handlers. It must provide an async iterator interface over incoming client messages while handling the Connect envelope protocol.

**Deliverables**:
- `AsyncClientStream[T]` class in new file `src/connectrpc/server_asgi_streams.py`
- Async iterator interface (`async def __aiter__`, `async def __anext__`)
- Integration with `AsyncEnvelopeParser` from Task 4
- Message deserialization and decompression
- Proper end-of-stream detection and error handling
- Access to request headers and metadata (like current `ClientStream`)

**Success Criteria ("Done")**:
- Unit tests pass for stream reading scenarios:
  - Async iteration over multiple client messages
  - Proper message deserialization (JSON and protobuf)
  - End-of-stream detection and cleanup
  - Error handling for malformed messages or connection issues
  - Access to request metadata and headers
- Integration test: Can read streaming messages from real Connect clients
- Compatibility test: Existing streaming handler logic works with async streams

**Files to Create/Modify**:
- `src/connectrpc/server_asgi_streams.py` (new)
- Tests: `tests/test_asgi_streams.py` (new)

---

### Task 13: Streaming Foundation - AsyncConnectStreamingRequest

**Description**: Implement streaming request validation for Connect streaming protocols.

**Context**: Streaming requests use different content types (`application/connect+json`, `application/connect+proto`) and headers (`connect-content-encoding`) compared to unary requests. The validation logic must handle these differences.

**Deliverables**:
- `AsyncConnectStreamingRequest` class in `src/connectrpc/server_asgi_requests.py`
- Validation for streaming content types and headers
- Connect streaming protocol compliance validation
- Integration with `AsyncClientStream` creation
- Error handling specific to streaming protocols

**Success Criteria ("Done")**:
- Unit tests pass for streaming validation:
  - Valid streaming requests (connect+json, connect+proto)
  - Invalid content types for streaming protocols
  - Proper header validation (connect-content-encoding)
  - Error response generation for streaming protocol violations
- Integration test: Validation works with real Connect streaming clients
- Conformance test: Behavior matches Connect protocol specification

**Files to Create/Modify**:
- `src/connectrpc/server_asgi_requests.py` (extend)
- Tests: `tests/test_asgi_requests.py` (extend)

---

### Task 14: Streaming Foundation - Response Handler

**Description**: Create streaming response handler that sends `AsyncIterator[T]` responses via ASGI events using envelope format.

**Context**: This handles the server side of streaming responses - taking an async iterator from user handlers and sending the messages via ASGI events using Connect's envelope protocol. Must handle both server streaming and bidirectional streaming response patterns.

**Deliverables**:
- Streaming response sender in `src/connectrpc/server_asgi_streams.py`
- Async iteration over user-provided `AsyncIterator[T]` 
- Message serialization and envelope formatting
- Integration with compression and Connect protocol
- Proper stream termination with `EndStreamResponse`
- Error handling and stream cleanup

**Success Criteria ("Done")**:
- Unit tests pass for streaming response scenarios:
  - Async iteration over handler response streams
  - Proper message serialization and envelope formatting
  - Stream termination with appropriate end-stream messages
  - Error handling when response iterators fail
  - Compression integration
- Integration test: Streaming responses are properly received by Connect clients
- Performance test: Efficiently handles large response streams

**Files to Create/Modify**:
- `src/connectrpc/server_asgi_streams.py` (extend)
- Tests: `tests/test_asgi_streams.py` (extend)

---

### Task 15: All Streaming Types - Server Streaming

**Description**: Implement server streaming RPC support (unary request → AsyncIterator response).

**Context**: Server streaming RPCs receive a single request message and return a stream of response messages. This is simpler than bidirectional streaming but requires integration of unary request processing with streaming response handling.

**Deliverables**:
- Server streaming support integrated into `ConnectASGI`
- Registration method: `register_server_streaming()`
- Request processing using unary request logic (Tasks 6-8)
- Response processing using streaming response logic (Task 14)
- Proper routing and handler dispatch

**Success Criteria ("Done")**:
- Unit tests pass for server streaming scenarios:
  - Successful server streaming RPC execution
  - Various response stream patterns (empty, single message, many messages)
  - Error handling in response streams
  - Proper Connect protocol compliance
- Integration test: Server streaming works with real Connect clients
- **Conformance test: Update config to include `STREAM_TYPE_SERVER_STREAM` and validate server streaming conformance tests pass**

**Files to Create/Modify**:
- `src/connectrpc/server_asgi.py` (extend)
- Tests: `tests/test_server_asgi.py` (extend)

---

### Task 16: All Streaming Types - Client Streaming

**Description**: Implement client streaming RPC support (AsyncClientStream → unary response).

**Context**: Client streaming RPCs receive a stream of request messages and return a single response message. This combines streaming request processing with unary response handling.

**Deliverables**:
- Client streaming support integrated into `ConnectASGI`
- Registration method: `register_client_streaming()`
- Request processing using `AsyncClientStream` (Task 12)
- Response processing using unary response logic (Task 8)
- Proper streaming request validation and routing

**Success Criteria ("Done")**:
- Unit tests pass for client streaming scenarios:
  - Successful client streaming RPC execution
  - Various request stream patterns (empty, single message, many messages)
  - Error handling in request streams
  - Proper response generation and sending
- Integration test: Client streaming works with real Connect clients
- **Conformance test: Update config to include `STREAM_TYPE_CLIENT_STREAM` and validate client streaming conformance tests pass**

**Files to Create/Modify**:
- `src/connectrpc/server_asgi.py` (extend)
- Tests: `tests/test_server_asgi.py` (extend)

---

### Task 17: All Streaming Types - Bidirectional Streaming with Full-Duplex

**Description**: Implement bidirectional streaming RPC support with true full-duplex capability.

**Context**: This is the most complex RPC type, requiring concurrent handling of request and response streams. Unlike the current WSGI implementation which is "half duplex only", this ASGI implementation should support true full-duplex streaming where reading and writing happen concurrently.

**Deliverables**:
- Bidirectional streaming support integrated into `ConnectASGI`
- Registration method: `register_bidi_streaming()`
- Full-duplex implementation using `asyncio.TaskGroup` or similar
- Concurrent request stream reading and response stream writing
- Proper error handling and resource cleanup for concurrent operations
- Performance optimization for high-throughput streaming

**Success Criteria ("Done")**:
- Unit tests pass for bidirectional streaming scenarios:
  - Successful bidirectional RPC execution with concurrent read/write
  - Various streaming patterns (echo, transform, selective response)
  - Error handling in both request and response streams
  - Proper stream termination and cleanup
- Integration test: True full-duplex operation (can send responses before consuming all requests)
- Performance test: Concurrent streaming outperforms half-duplex implementation
- **Conformance test: Update config to include `STREAM_TYPE_HALF_DUPLEX_BIDI_STREAM`, validate full-duplex capabilities exceed WSGI implementation**

**Files to Create/Modify**:
- `src/connectrpc/server_asgi.py` (extend)
- `src/connectrpc/server_asgi_streams.py` (extend)
- Tests: `tests/test_server_asgi.py` (extend)
- Tests: `tests/test_asgi_streams.py` (extend)

---

## Phase 4: Code Generation

### Task 18: Code Generation - ASGI Constructor Functions

**Description**: Extend the existing protobuf code generator to create ASGI constructor functions alongside the existing WSGI ones.

**Context**: The current generator (`src/connectrpc/generator.py`) creates WSGI constructor functions like `wsgi_eliza_service()`. We need equivalent ASGI functions that return properly configured `ConnectASGI` instances.

**Deliverables**:
- ASGI constructor generation integrated into existing generator
- Generated functions like `asgi_eliza_service(implementation) -> ConnectASGI`
- Automatic registration of all service methods with correct RPC types
- Integration with existing code generation infrastructure
- Backward compatibility with existing WSGI generation

**Success Criteria ("Done")**:
- Unit tests pass for code generation:
  - ASGI constructor functions are generated for all service types
  - Generated functions create properly configured `ConnectASGI` instances
  - All RPC methods are correctly registered with appropriate types
  - Generated code compiles and passes type checking
- Integration test: Generated ASGI services work with real clients
- Regression test: WSGI generation continues to work unchanged

**Files to Create/Modify**:
- `src/connectrpc/generator.py` (extend)
- Tests: `tests/test_generator.py` (extend)

---

### Task 19: Code Generation - Async Protocol Interfaces

**Description**: Generate async Protocol interfaces for all RPC types that service implementations must satisfy.

**Context**: The current generator creates sync Protocol interfaces. We need async versions that use `AsyncClientStream[T]` and `AsyncIterator[T]` for streaming RPCs while maintaining type safety and clear user interfaces.

**Deliverables**:
- Async Protocol interface generation in existing generator
- Protocol interfaces for all RPC types:
  - Unary: `async def method(req: ClientRequest[T]) -> ServerResponse[U]`
  - Server streaming: `async def method(req: ClientRequest[T]) -> AsyncIterator[U]`
  - Client streaming: `async def method(req: AsyncClientStream[T]) -> ServerResponse[U]`
  - Bidirectional: `async def method(req: AsyncClientStream[T]) -> AsyncIterator[U]`
- Type annotations and proper generic constraints
- Integration with existing type system and imports

**Success Criteria ("Done")**:
- Unit tests pass for protocol generation:
  - Correct async Protocol interfaces generated for all RPC types
  - Proper type annotations with generic constraints
  - Generated protocols pass mypy type checking
  - Compatible with user implementation classes
- Integration test: Users can implement generated protocols correctly
- Type checking test: Generated code passes strict type checking

**Files to Create/Modify**:
- `src/connectrpc/generator.py` (extend)
- Tests: `tests/test_generator.py` (extend)

---

## Phase 5: Testing & Validation

### Task 20: Testing Infrastructure - ASGI Test Server Setup

**Description**: Create comprehensive testing infrastructure for ASGI implementation using real ASGI servers.

**Context**: We need to test the ASGI implementation with real servers (uvicorn, hypercorn) to ensure compatibility and performance. This includes both unit testing utilities and integration test setup.

**Deliverables**:
- ASGI test server utilities in `tests/test_utils_asgi.py`
- Integration with uvicorn/hypercorn for testing
- Test client utilities for making requests to ASGI servers
- Performance testing infrastructure
- Utilities for testing concurrent streaming scenarios

**Success Criteria ("Done")**:
- Test infrastructure supports all testing scenarios:
  - Unit tests with mock ASGI interfaces
  - Integration tests with real ASGI servers
  - Performance tests for throughput and latency
  - Concurrent streaming test utilities
- All existing functionality works with test infrastructure
- Performance tests demonstrate ASGI advantages over WSGI (especially for streaming)

**Files to Create/Modify**:
- `tests/test_utils_asgi.py` (new)
- `tests/conftest.py` (extend with ASGI fixtures)

---

### Task 21: Testing Infrastructure - Conformance Test Adaptation

**Description**: Adapt the existing comprehensive conformance tests to validate the ASGI implementation.

**Context**: The existing conformance tests (`tests/conformance/`) provide comprehensive validation of Connect protocol compliance. These tests need to be adapted to run against the ASGI implementation while maintaining the same level of coverage.

**Deliverables**:
- ASGI conformance test server implementation
- Adaptation of existing conformance tests for ASGI
- Full protocol compliance validation for all RPC types
- Performance comparison tests (ASGI vs WSGI)
- Streaming-specific tests that demonstrate full-duplex capabilities

**Success Criteria ("Done")**:
- Conformance tests pass for ASGI implementation:
  - All existing WSGI conformance tests pass with ASGI
  - Additional ASGI-specific tests pass (full-duplex streaming)
  - Performance tests show expected improvements
  - Protocol compliance matches or exceeds WSGI implementation
- Integration test: ASGI implementation interoperates with existing Connect clients
- Regression test: ASGI and WSGI implementations have identical protocol behavior

**Files to Create/Modify**:
- `tests/conformance/conformance_server_asgi.py` (new)
- `tests/conformance/test_conformance_asgi.py` (new)
- Existing conformance test files (adapt for ASGI)

---

## Phase 6: Polish & Integration

### Task 22: Production Readiness - Error Handling and Logging

**Description**: Add comprehensive error handling, logging, and monitoring capabilities for production use.

**Context**: Production ASGI servers need robust error handling, comprehensive logging, and integration with monitoring systems. This includes proper exception handling, performance metrics, and debugging capabilities.

**Deliverables**:
- Comprehensive error handling throughout ASGI implementation
- Structured logging with appropriate log levels
- Performance metrics and monitoring hooks
- Debugging utilities for development
- Integration with common Python logging and monitoring frameworks

**Success Criteria ("Done")**:
- Error handling covers all failure scenarios:
  - Connection errors and timeouts
  - Handler exceptions and recovery
  - Protocol violations and malformed requests
  - Resource exhaustion and backpressure
- Logging provides actionable information for debugging and monitoring
- Performance metrics enable production monitoring and optimization

**Files to Create/Modify**:
- All ASGI implementation files (add logging and error handling)
- `src/connectrpc/server_asgi_monitoring.py` (new)

---

### Task 23: Production Readiness - Documentation and Examples

**Description**: Create comprehensive documentation and usage examples for the ASGI implementation.

**Context**: Users need clear documentation on how to use the ASGI implementation, migrate from WSGI, and take advantage of new capabilities like full-duplex streaming.

**Deliverables**:
- User documentation for ASGI implementation
- Migration guide from WSGI to ASGI  
- Examples demonstrating all RPC types
- Performance tuning guide
- Integration examples with popular ASGI servers
- API reference documentation

**Success Criteria ("Done")**:
- Documentation enables users to successfully adopt ASGI implementation:
  - Clear getting started guide
  - Working examples for all RPC types
  - Migration path from existing WSGI implementations
  - Performance optimization guidance
- Examples demonstrate advantages of ASGI (especially full-duplex streaming)
- API documentation is complete and accurate

**Files to Create/Modify**:
- `docs/asgi_guide.md` (new)
- `examples/asgi_server.py` (new)
- `examples/full_duplex_streaming.py` (new)
- README updates with ASGI information

---

## Phase 7: WSGI Implementation Cleanup

### Task 24: WSGI Compression Architecture Cleanup

**Description**: Refactor the existing WSGI StreamReader to remove low-level compression handling and move it to the appropriate request processing layers.

**Context**: During ASGI implementation, we discovered that compression should be handled differently for unary vs streaming RPCs. The current WSGI `StreamReader` class handles decompression at the I/O level, but this is architecturally incorrect. For unary requests, decompression should happen after reading the complete body. For streaming requests, decompression happens per envelope.

**Deliverables**:
- Remove decompressor integration from `StreamReader` class in `src/connectrpc/io.py`
- Update `ConnectUnaryRequest` to handle decompression after reading complete body
- Update streaming envelope parsing to handle decompression per message (if not already correct)
- Ensure existing WSGI functionality remains intact
- Update any affected tests

**Success Criteria ("Done")**:
- Unit tests pass for existing WSGI functionality:
  - Unary requests with compressed bodies work correctly  
  - Streaming requests with compressed envelopes work correctly
  - All existing compression formats (gzip, brotli, zstd) continue to work
  - No regression in WSGI performance or functionality
- Architecture consistency: WSGI and ASGI implementations handle compression at the same level
- Code clarity: Compression logic is in the appropriate layer for each RPC type

**Files to Create/Modify**:
- `src/connectrpc/io.py` (modify StreamReader)
- `src/connectrpc/server_requests.py` (update ConnectUnaryRequest)
- Tests: Update existing tests as needed

---

### Task 25: Synchronous Envelope Parser for WSGI and Client Use

**Description**: Port the AsyncEnvelopeParser implementation to create a synchronous version for use in WSGI servers and Connect clients.

**Context**: The AsyncEnvelopeParser implemented in Task 4 (commit ccc7bad) provides a clean, well-tested envelope parsing implementation for Connect protocol streaming. This same logic should be available for synchronous use cases:
1. WSGI streaming requests (to replace the current inline parsing in `ClientStream.from_client_req`)
2. Connect client streaming responses (currently handled inline in client code)
3. Consistency between async and sync implementations

**Reference Implementation**: See `AsyncEnvelopeParser` in `src/connectrpc/connect_async_io.py` (commit ccc7bad)

**Deliverables**:
- `SyncEnvelopeParser` class in `src/connectrpc/connect_sync_io.py` (new file)
- Same interface as `AsyncEnvelopeParser` but works with sync `Stream` objects from `src/connectrpc/io.py`
- `EnvelopeData` class can be shared between async and sync implementations
- Integration with existing `StreamReader` class for reading envelope data
- Proper error handling matching the async implementation
- Support for all compression codecs

**Success Criteria ("Done")**:
- Unit tests pass for sync envelope parsing scenarios:
  - All test cases from `AsyncEnvelopeParser` ported to sync version
  - Compressed and uncompressed envelopes work correctly
  - End-stream detection and error handling
  - Integration with existing `StreamReader` and compression systems
- Integration test: Can parse envelopes from existing WSGI streaming requests
- Refactoring opportunity: Replace inline parsing in `ClientStream.from_client_req` with new parser
- Architecture consistency: Sync and async envelope parsing have identical behavior

**Files to Create/Modify**:
- `src/connectrpc/connect_sync_io.py` (new)
- Tests: `tests/test_connect_sync_io.py` (new)
- Optional: Refactor `src/connectrpc/server.py` to use new parser
- Optional: Refactor client streaming code to use new parser

**Dependencies**: Should be completed after Task 24 (WSGI Compression Architecture Cleanup) to ensure consistent compression handling across sync and async implementations.

---

## Session Planning

**Recommended session breakdown with incremental conformance testing:**

1. **Session 1**: Tasks 1-3 (ASGI Event Primitives)
2. **Session 2**: Tasks 4-5 (Connect Protocol Async I/O)  
3. **Session 3**: Tasks 6-8 (Unary RPC Implementation)
4. **Session 4**: Tasks 9, 9.5, 10 (ConnectASGI Core + Conformance Infrastructure + Routing) - **Milestone: Working Unary RPCs with Basic Conformance**
5. **Session 5**: Task 11 (Connection Lifecycle) - **Milestone: Complete Unary Conformance**
6. **Session 6**: Tasks 12-14 (Streaming Foundation)
7. **Session 7**: Task 15 (Server Streaming) - **Milestone: Server Streaming Conformance**
8. **Session 8**: Task 16 (Client Streaming) - **Milestone: Client Streaming Conformance**  
9. **Session 9**: Task 17 (Bidirectional Streaming) - **Milestone: Full-duplex Streaming Conformance**
10. **Session 10**: Tasks 18-19 (Code Generation)
11. **Session 11**: Tasks 20-21 (Testing & Validation - now focused on performance and edge cases)
12. **Session 12**: Tasks 22-23 (Production Readiness)

**Key Changes:**
- **Early Conformance**: Task 9.5 introduces conformance testing infrastructure immediately after basic ASGI implementation
- **Incremental Validation**: Each streaming milestone includes updating conformance config and validating new RPC types
- **Continuous Validation**: Conformance tests run throughout development rather than waiting until Task 21
- **Faster Feedback**: Protocol compliance issues are caught early rather than at the end

Each session should result in working, tested code that passes conformance tests for the implemented features.
