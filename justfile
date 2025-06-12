# Run mypy type checking
mypy:
    mypy src tests

# Format code with ruff
format:
    ruff format src tests

# Check code with ruff linter
check:
    ruff check src tests

# Run all checks (format, check, mypy)
all: format check mypy