import sys

try:
    import protogen
    from connectrpc.generator.generator import generate
except ImportError as e:
    print(f"Error: Missing compiler dependencies. Install with: pip install connect-python[compiler]", file=sys.stderr)
    print(f"Import error: {e}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    opts = protogen.Options()
    opts.run(generate)


if __name__ == "__main__":
    main()