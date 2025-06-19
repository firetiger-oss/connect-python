# Run mypy type checking
mypy: mypy-package mypy-tests

mypy-package:
    mypy --package connectrpc

mypy-tests:
    MYPYPATH=tests/conformance mypy --module conformance_client --module connectrpc.conformance.v1.service_pb2_connect

# Format code with ruff
format:
    ruff format src tests examples

# Check code with ruff linter
check:
    ruff check src tests examples

# Fix auto-fixable ruff linter issues
fix:
    ruff check src tests examples --fix

# Run tests
test:
    uv run pytest

# Run integration test against demo.connectrpc.com
integration-test:
    cd examples && uv run python eliza_integration_test.py --protocols connect-proto connect-json

# Run protoc with connect_python plugin (development mode). usage: just protoc-gen [PROTOC_ARGS...]
protoc-gen *ARGS:
    protoc --plugin=protoc-gen-connect_python=.venv/bin/protoc-gen-connect_python {{ARGS}}

generate:
    cd tests/conformance && buf generate
    cd examples && buf generate    

# Run conformance tests (requires connectconformance binary). Usage: just conformance-test [ARGS...]
conformance-test *ARGS:
    #!/usr/bin/env bash
    set -euo pipefail
    if ! command -v connectconformance &> /dev/null; then
        echo "Error: connectconformance binary not found in PATH"
        echo "Please install it with: go install connectrpc.com/conformance/cmd/connectconformance@latest"
        echo "Or download from: https://github.com/connectrpc/conformance/releases"
        exit 1
    fi
    cd tests/conformance

    buf generate

    connectconformance \
        --conf ./config.yaml \
        --mode client \
        --known-failing="Client Cancellation/**" \
        {{ARGS}} \
        -- \
    	uv run python conformance_client.py

# Run all checks (format, check, mypy, test, integration-test)
all: format check mypy test integration-test
