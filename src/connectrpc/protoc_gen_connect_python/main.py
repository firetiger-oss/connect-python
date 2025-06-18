import sys

try:
    import protogen

    from connectrpc.generator import generate
except ImportError as e:
    print(
        "Error: Missing compiler dependencies. Install with: pip install connect-python[compiler]",
        file=sys.stderr,
    )
    print(f"Import error: {e}", file=sys.stderr)
    sys.exit(1)

from google.protobuf.compiler import plugin_pb2


def main() -> None:
    opts = protogen.Options(
        supported_features=[
            plugin_pb2.CodeGeneratorResponse.Feature.FEATURE_PROTO3_OPTIONAL,  # type: ignore[list-item]
        ]
    )
    opts.run(generate)


if __name__ == "__main__":
    main()
