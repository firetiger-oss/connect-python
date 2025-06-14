### Development

Set up development dependencies:
```sh
uv sync --extra dev
```

Install the package in editable mode to produce a local `protoc-gen-connect_python` plugin for use with `protoc`:
```sh
uv pip install -e .
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
