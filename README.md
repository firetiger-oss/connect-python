### Development

Set up development dependencies:
```
uv sync --extra dev
```

Then, use `uv run just` to do development checks:
```
 uv run just --list
 Available recipes:
    all              # Run all checks (format, check, mypy, test, integration-test)
    check            # Check code with ruff linter
    fix              # Fix auto-fixable ruff linter issues
    format           # Format code with ruff
    integration-test # Run integration test against demo.connectrpc.com
    mypy             # Run mypy type checking
    test             # Run tests
```

For example, `uv run check` will lint code.
