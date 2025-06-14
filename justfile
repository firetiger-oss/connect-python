# Run mypy type checking
mypy:
    mypy src tests examples

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

# Run all checks (format, check, mypy, test, integration-test)
all: format check mypy test integration-test