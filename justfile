# Run mypy type checking
mypy:
    mypy src tests

# Format code with ruff
format:
    ruff format src tests

# Check code with ruff linter
check:
    ruff check src tests

fix:
    ruff check src tests --fix

# Run tests
test:
    uv run pytest

# Run integration test against demo.connectrpc.com
integration-test:
    cd examples && uv run python eliza_integration_test.py --protocols connect-proto

# Run integration test with all protocols
integration-test-all:
    cd examples && uv run python eliza_integration_test.py --protocols connect-proto connect-json grpc grpc-web

# Run all checks (format, check, mypy)
all: format check mypy test integration-test