# Connect Python

A Python implementation of the Connect RPC framework.

## Installation

For basic client functionality:
```bash
pip install connect-python
```

For code generation (protoc plugin):
```bash
pip install connect-python[compiler]
```

### Development

Set up development dependencies:
```sh
uv sync --extra dev --extra compiler
```

Install the package in editable mode to produce a local `protoc-gen-connect_python` plugin for use with `protoc`:
```sh
uv pip install -e .[compiler]
```

Then, use `uv run just` to do development checks:
```
Available recipes:
    all              # Run all checks (format, check, mypy, test, integration-test)
    check            # Check code with ruff linter
    fix              # Fix auto-fixable ruff linter issues
    format           # Format code with ruff
    integration-test # Run integration test against demo.connectrpc.com
    mypy             # Run mypy type checking
    protoc-gen *ARGS # Run protoc with connect_python plugin (development mode). usage: just protoc-gen [PROTOC_ARGS...]
    test             # Run tests
```

For example, `uv run check` will lint code.
