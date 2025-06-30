# Development

## Setting Up Development Environment

### Prerequisites

- Python 3.10 or later
- [uv](https://docs.astral.sh/uv/) for dependency management

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/firetiger-oss/connect-python.git
   cd connect-python
   ```

2. Install dependencies:
   ```bash
   uv sync --extra dev --extra compiler
   ```

3. Install the package in editable mode:
   ```bash
   uv pip install -e .[compiler]
   ```

## Development Workflow

We use `just` as a task runner. Available commands:

```bash
# Format code
just format

# Check code with linter
just check

# Fix auto-fixable issues
just fix

# Run type checking
just mypy

# Run tests
just test

# Run integration tests
just integration-test

# Run conformance tests
just conformance-test

# Run all checks
just all
```

## Code Style

We use:
- **ruff** for linting and formatting
- **mypy** for type checking
- **pytest** for testing

The project follows strict type checking and formatting standards.

## Testing

### Unit Tests

```bash
just test
```

### Integration Tests

```bash
just integration-test
```

### Conformance Tests

The project uses the official Connect conformance test suite:

```bash
# Install conformance test runner
go install connectrpc.com/conformance/cmd/connectconformance@latest

# Run all conformance tests
just conformance-test

# Run specific conformance tests
just conformance-test-client-async
just conformance-test-client-sync
just conformance-test-server-sync
```

## Code Generation

The project includes protobuf code generation for examples and tests:

```bash
just generate
```

## Documentation

### Building Documentation

```bash
# Build documentation
just docs

# Serve documentation locally
just docs-serve
```

### Writing Documentation

- Use MyST markdown for documentation files
- Place API documentation in `docs/api/`
- Place examples in `docs/examples/`
- Update the main `docs/index.md` for structural changes

## Release Process

See the `devdocs/releases.md` file in the repository for detailed release procedures.

### Quick Release Commands

```bash
# Patch release
uv run bump-my-version bump patch

# Minor release  
uv run bump-my-version bump minor

# Major release
uv run bump-my-version bump major
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run the full test suite: `just all`
5. Submit a pull request

### Pull Request Guidelines

- Ensure all tests pass
- Add tests for new functionality
- Update documentation as needed
- Follow the existing code style
- Write clear commit messages