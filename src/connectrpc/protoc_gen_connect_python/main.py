import sys

try:
    from connectrpc.generator.generator import invoke
except ImportError as e:
    print(
        "Error: Missing compiler dependencies. Install with: pip install connect-python[compiler]",
        file=sys.stderr,
    )
    print(f"Import error: {e}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    invoke(sys.stdin.buffer, sys.stdout.buffer)


if __name__ == "__main__":
    main()
