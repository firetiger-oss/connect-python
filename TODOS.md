# Connect Python Client TODO List

## High Priority Client Implementations

### 2. Implement ConnectGRPCClient  
- gRPC over HTTP/2 protocol implementation
- Support for standard gRPC wire format
- Binary protobuf encoding with gRPC framing
- All RPC types with proper gRPC semantics

### 3. Implement ConnectGRPCWebClient
- gRPC-Web protocol implementation  
- Support for gRPC-Web framing format
- Compatible with gRPC-Web proxies and browsers
- Unary and server streaming (gRPC-Web limitations)

## High Priority Protocol Features

### 7. Implement Connect Error Model
- Complete error code enumeration (canceled, unknown, invalid_argument, etc.)
- HTTP status code to Connect error code mapping
- Proper error serialization/deserialization
- Error details support with protobuf Any messages
- ConnectError exception hierarchy

## Medium Priority Features

### 8. Implement Compression Codecs
- **gzip**: Standard gzip compression
- **br**: Brotli compression  
- **zstd**: Zstandard compression
- **identity**: No compression (passthrough)
- Content-Encoding and Accept-Encoding header handling
- Streaming compression support

### 9. Add Unary Metadata Support
- **Leading metadata**: Custom headers sent with request
- **Trailing metadata**: Headers sent with response (prefixed with "trailer-")
- ASCII and binary metadata handling
- Base64 encoding for binary metadata (keys ending in "-bin")
- Metadata extraction from HTTP headers

### 10. Add Connect-Timeout-Ms Header Support
- Timeout specification in milliseconds
- Client-side timeout configuration
- Server-side timeout enforcement
- Proper timeout error handling

## Low Priority Features

### 11. Implement GET Request Support
- Support for side-effect-free unary RPCs
- Query parameter encoding: `?message=...&encoding=...&connect=v1`
- Base64 encoding for binary payloads (`&base64=1`)
- Compression support for GET requests
- Proper caching behavior for GET requests

### 12. Add Response Metadata Extraction
- Extract response headers as metadata
- Handle both leading and trailing metadata
- Provide access to HTTP response metadata
- Support for custom metadata handling

## Error Codes to Implement

Based on Connect Protocol specification:

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `canceled` | 499 | RPC canceled by caller |
| `unknown` | 500 | Catch-all for unclear errors |
| `invalid_argument` | 400 | Invalid request regardless of system state |
| `deadline_exceeded` | 504 | Deadline expired before completion |
| `not_found` | 404 | Requested resource not found |
| `already_exists` | 409 | Resource already exists |
| `permission_denied` | 403 | Not authorized to perform operation |
| `resource_exhausted` | 429 | Resource exhausted |
| `failed_precondition` | 400 | System not in required state |
| `aborted` | 409 | Operation aborted (concurrency issues) |
| `out_of_range` | 400 | Operation attempted past valid range |
| `unimplemented` | 501 | Operation not implemented |
| `internal` | 500 | Internal system error |
| `unavailable` | 503 | Service temporarily unavailable |
| `data_loss` | 500 | Unrecoverable data loss |
| `unauthenticated` | 401 | Invalid authentication credentials |
