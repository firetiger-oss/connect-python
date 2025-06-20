# Connect Python Conformance Test Fixes TODO

This document outlines the specific issues that need to be fixed to pass the Connect protocol conformance tests. Based on analysis of the test run on 2025-06-17, there are 98 failing test cases out of 203 total.

## Current Status
- **Total test cases**: 203
- **Passing**: 105
- **Failing**: 98
- **Test command**: `uv run just conformance-test`

## ✅ COMPLETED: Header Handling - Multiple Values Not Supported
**Status**: **FIXED** - Multi-valued headers now working

**What was done**:
- Added multidict dependency to pyproject.toml
- Created src/connectrpc/headers.py with HeaderInput type system  
- Updated all client layers to use CIMultiDict internally
- Fixed conformance client request_headers() to preserve all values
- Regenerated service clients with new HeaderInput signatures

**Verification**: The error "expected ["Value1", "Value2"], got ["Value1"]" no longer appears in conformance tests.

## ~~High Priority Issues~~

### ~~1. Header Handling - Multiple Values Not Supported~~
~~**Files to modify**: `tests/conformance/conformance_client.py:126-127`~~

~~**Issue**: The `request_headers()` function only takes the first value from each header, but conformance tests expect multiple values per header name.~~

~~**Expected behavior**: Headers like `x-conformance-test` should include all values: `["Value1", "Value2"]`~~

~~**Fix needed**: Change return type to `dict[str, list[str]]` and handle multiple values correctly. Update all call sites to handle list values.~~ **✅ COMPLETED**

### 2. Missing Response Headers and Trailers
**Files to modify**: 
- `src/connectrpc/client_connect.py` (ConnectAsyncStreamOutput class)
- `tests/conformance/conformance_client.py` (response handling)

**Issue**: Response headers (`x-custom-header`) and trailers (`x-custom-trailer`) are not being captured from server responses.

**Current behavior**: Tests report "actual response headers missing 'x-custom-header'" and "actual response trailers missing 'x-custom-trailer'"

**Expected behavior**: Client should capture and expose response headers and trailing metadata

**Fix needed**: 
1. Extract response headers from `aiohttp.ClientResponse` in unary calls
2. Properly expose trailing metadata from `ConnectAsyncStreamOutput.trailing_metadata()`
3. Update conformance client to populate response headers/trailers in `ClientCompatResponse`

### 3. Streaming Response Handling - Empty Responses
**Files to modify**: `tests/conformance/conformance_client.py` (streaming method handlers)

**Issue**: Many streaming tests return "client returned a response with neither an error nor result"

**Affected methods**: 
- ServerStream (lines 67-81)
- BidiStream (lines 100-115) 
- Client cancellation tests
- Error handling tests

**Current behavior**: `response.response.payloads` remains empty even when server sends data

**Expected behavior**: Stream responses should populate `response.response.payloads` with received messages

**Fix needed**: 
1. Ensure streaming loops properly collect all response messages
2. Handle EndStreamResponse correctly to capture trailing metadata and errors
3. Verify `async for` loops are consuming the entire stream

### 4. Bidirectional Streaming Complete Failure
**Files to modify**: 
- `src/connectrpc/client_connect.py` (bidirectional streaming implementation)
- `tests/conformance/conformance_client.py:100-115`

**Issue**: All bidirectional streaming tests fail with empty responses, including "half-duplex" mode tests

**Current behavior**: `bidi_stream()` method returns no data

**Expected behavior**: Should handle bidirectional message exchange, including half-duplex mode where client sends all messages before reading responses

**Fix needed**:
1. Verify bidirectional streaming implementation in `AsyncConnectProtocolClient`
2. Ensure conformance client properly handles request/response flow
3. Add support for half-duplex mode (send all requests, then read all responses)

### 5. Timeout Handling Missing
**Files to modify**: 
- `src/connectrpc/client_connect.py` (add timeout support)
- `tests/conformance/conformance_client.py` (extract timeout from request)

**Issue**: Timeout tests expect error responses but receive successful responses with data

**Failing examples**:
- `Timeouts/.../unary: expecting an error but received none`
- `Timeouts/.../server-stream: expecting 0 response messages but instead got 2`

**Expected behavior**: When timeout is specified, client should send `Connect-Timeout-Ms` header and handle timeout errors

**Fix needed**:
1. Extract timeout from `ClientCompatRequest.timeout_ms` 
2. Add `Connect-Timeout-Ms` header to requests
3. Handle timeout errors properly (should return `CODE_DEADLINE_EXCEEDED`)

### 6. Unimplemented Method Support
**Files to modify**: `tests/conformance/conformance_client.py:117-118`

**Issue**: `Unimplemented` method test raises `NotImplementedError` instead of calling the service

**Current code**:
```python
else:
    raise NotImplementedError(f"not implemented: {request.method}")
```

**Expected behavior**: Should call `client.unimplemented()` method (which exists in the generated client at line 75-77)

**Fix needed**: Add handling for `request.method == "Unimplemented"` to call the appropriate client method

## Medium Priority Issues

### 7. Response Structure Population
**Files to modify**: `tests/conformance/conformance_client.py` (all method handlers)

**Issue**: Some test cases result in empty `ClientCompatResponse` objects

**Root causes**:
1. Exception handling that doesn't populate response fields
2. Streaming loops that exit early without collecting data
3. Error cases that don't set `response.error`

**Fix needed**: Ensure all code paths populate either `response.response.payloads` or `response.error`

### 8. Error Handling in Streaming
**Files to modify**: 
- `src/connectrpc/streams_connect.py` (EndStreamResponse handling)
- `tests/conformance/conformance_client.py` (streaming error handling)

**Issue**: Some error tests expect specific error responses but get different results

**Examples**:
- `expecting 2 response messages but instead got 0`
- Server should send partial responses then an error

**Fix needed**: Verify EndStreamResponse error handling preserves partial results before raising errors

## Implementation Notes

### Test Patterns
The conformance tests follow these patterns:
- **Basic tests**: Verify core functionality works
- **Client Cancellation**: Test cancellation behavior  
- **Duplicate Metadata**: Test header handling with multiple values
- **Errors**: Test error propagation in streaming
- **Timeouts**: Test timeout handling

### Code Organization
- **Conformance client**: `tests/conformance/conformance_client.py` - handles test execution
- **Generated service client**: `tests/conformance/connectrpc/conformance/v1/service_pb2_connect.py` - protocol-specific client
- **Core client**: `src/connectrpc/client.py` - main client facade
- **Protocol implementation**: `src/connectrpc/client_connect.py` - Connect protocol specifics

### Testing Approach
1. Fix one category at a time (start with headers)
2. Run `uv run just conformance-test` after each fix
3. Look for reduced failure count and changed error messages
4. Focus on the most common error patterns first

### Success Criteria
- All 203 test cases should pass
- No "client returned a response with neither an error nor result" errors
- Proper header/trailer handling
- Correct timeout and error behavior

## Next Steps
1. Start with **Header Handling** (affects most tests)
2. Then **Streaming Response Handling** 
3. Then **Timeout Support**
4. Finally **Bidirectional Streaming** and **Error Handling**

This approach should systematically eliminate the 98 failing test cases.
