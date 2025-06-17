import protogen


def _generate_unary_rpc(
    g: protogen.GeneratedFile, f: protogen.File, s: protogen.Service, m: protogen.Method
) -> None:
    """Generate a unary RPC method."""
    g.P(
        "async def ",
        m.py_name,
        "(self, req: ",
        m.input.py_ident,
        ", extra_headers: HeaderInput | None=None) -> ",
        m.output.py_ident,
        ":",
    )
    g.set_indent(8)
    g.P('url = self.base_url + "/', f.proto.package, ".", s.proto.name, "/", m.proto.name, '"')
    g.P(
        "return await self._connect_client.call_unary(url, req, ",
        m.output.py_ident,
        ", extra_headers)",
    )
    g.set_indent(4)
    g.P()


def _generate_server_streaming_rpc(
    g: protogen.GeneratedFile, f: protogen.File, s: protogen.Service, m: protogen.Method
) -> None:
    """Generate a server streaming RPC with dual API pattern."""
    # Simple iterator method
    g.P("def ", m.py_name, "(")
    g.P("    self, req: ", m.input.py_ident, ", extra_headers: HeaderInput | None=None")
    g.P(") -> AsyncIterator[", m.output.py_ident, "]:")
    g.P("    return self._", m.py_name, "_impl(req, extra_headers)")
    g.P()

    # Implementation helper
    g.P("async def _", m.py_name, "_impl(")
    g.P("    self, req: ", m.input.py_ident, ", extra_headers: HeaderInput | None=None")
    g.P(") -> AsyncIterator[", m.output.py_ident, "]:")
    g.set_indent(8)
    g.P("async with await self.", m.py_name, "_stream(req, extra_headers) as stream:")
    g.set_indent(12)
    g.P("async for response in stream:")
    g.set_indent(16)
    g.P("yield response")
    g.set_indent(4)
    g.P()

    # Stream method for metadata access
    g.P("async def ", m.py_name, "_stream(")
    g.P("    self, req: ", m.input.py_ident, ", extra_headers: HeaderInput | None=None")
    g.P(") -> StreamOutput[", m.output.py_ident, "]:")
    g.set_indent(8)
    g.P('url = self.base_url + "/', f.proto.package, ".", s.proto.name, "/", m.proto.name, '"')
    g.P("return await self._connect_client.call_server_streaming(")
    g.P("    url, req, ", m.output.py_ident, ", extra_headers")
    g.P(")")
    g.set_indent(4)
    g.P()


def _generate_client_streaming_rpc(
    g: protogen.GeneratedFile, f: protogen.File, s: protogen.Service, m: protogen.Method
) -> None:
    """Generate a client streaming RPC method."""
    g.P("async def ", m.py_name, "(")
    g.P(
        "    self, reqs: StreamInput[",
        m.input.py_ident,
        "]",
        ", extra_headers: HeaderInput | None=None",
    )
    g.P(") -> ", m.output.py_ident, ":")
    g.set_indent(8)
    g.P('url = self.base_url + "/', f.proto.package, ".", s.proto.name, "/", m.proto.name, '"')
    g.P("return await self._connect_client.call_client_streaming(")
    g.P("    url, reqs, ", m.output.py_ident, ", extra_headers")
    g.P(")")
    g.set_indent(4)
    g.P()


def _generate_bidirectional_streaming_rpc(
    g: protogen.GeneratedFile, f: protogen.File, s: protogen.Service, m: protogen.Method
) -> None:
    """Generate a bidirectional streaming RPC with dual API pattern."""
    # Simple iterator method
    g.P("def ", m.py_name, "(")
    g.P(
        "    self, reqs: StreamInput[",
        m.input.py_ident,
        "]",
        ", extra_headers: HeaderInput | None=None",
    )
    g.P(") -> AsyncIterator[", m.output.py_ident, "]:")
    g.P("    return self._", m.py_name, "_impl(reqs, extra_headers)")
    g.P()

    # Implementation helper
    g.P("async def _", m.py_name, "_impl(")
    g.P(
        "    self, reqs: StreamInput[",
        m.input.py_ident,
        "]",
        ", extra_headers: HeaderInput | None=None",
    )
    g.P(") -> AsyncIterator[", m.output.py_ident, "]:")
    g.set_indent(8)
    g.P("async with await self.", m.py_name, "_stream(reqs, extra_headers) as stream:")
    g.set_indent(12)
    g.P("async for response in stream:")
    g.set_indent(16)
    g.P("yield response")
    g.set_indent(4)
    g.P()

    # Stream method for metadata access
    g.P("async def ", m.py_name, "_stream(")
    g.P(
        "    self, reqs: StreamInput[",
        m.input.py_ident,
        "]",
        ", extra_headers: HeaderInput | None=None",
    )
    g.P(") -> StreamOutput[", m.output.py_ident, "]:")
    g.set_indent(8)
    g.P('url = self.base_url + "/', f.proto.package, ".", s.proto.name, "/", m.proto.name, '"')
    g.P("return await self._connect_client.call_bidirectional_streaming(")
    g.P("    url, reqs, ", m.output.py_ident, ", extra_headers")
    g.P(")")
    g.set_indent(4)
    g.P()


def generate(gen: protogen.Plugin) -> None:
    for f in gen.files_to_generate:
        if len(f.services) == 0:
            continue

        import_path = protogen.PyImportPath(f.py_import_path._path + "_connect")
        g = gen.new_generated_file(
            f.proto.name.replace(".proto", "_pb2_connect.py"),
            import_path,
        )
        g.P("# Generated Connect client code")
        g.P()
        g.P("from collections.abc import AsyncIterator")
        g.P("import aiohttp")
        g.P()
        g.P("from connectrpc.client import ConnectClient")
        g.P("from connectrpc.client import ConnectProtocol")
        g.P("from connectrpc.headers import HeaderInput")
        g.P("from connectrpc.streams import StreamInput")
        g.P("from connectrpc.streams import StreamOutput")
        g.P()
        g.print_import()
        g.P()

        for s in f.services:
            g.P("class ", protogen.PyIdent(import_path, s.proto.name), "Client:")
            g.set_indent(4)
            g.P("def __init__(")
            g.P("    self,")
            g.P("    base_url: str,")
            g.P("    http_client: aiohttp.ClientSession | None = None,")
            g.P("    protocol: ConnectProtocol = ConnectProtocol.CONNECT_PROTOBUF,")
            g.P("):")
            g.P("    self.base_url = base_url")
            g.P("    self._connect_client = ConnectClient(http_client, protocol)")
            g.P()

            # Generate methods for each RPC
            for m in s.methods:
                # Assert that method input/output types are resolved
                assert m.input is not None, f"Method {m.py_name} input should be resolved"
                assert m.output is not None, f"Method {m.py_name} output should be resolved"

                if not m.proto.client_streaming and not m.proto.server_streaming:
                    _generate_unary_rpc(g, f, s, m)
                elif not m.proto.client_streaming and m.proto.server_streaming:
                    _generate_server_streaming_rpc(g, f, s, m)
                elif m.proto.client_streaming and not m.proto.server_streaming:
                    _generate_client_streaming_rpc(g, f, s, m)
                elif m.proto.client_streaming and m.proto.server_streaming:
                    _generate_bidirectional_streaming_rpc(g, f, s, m)

            g.set_indent(0)
            g.P()


def gather_message_types(g: protogen.GeneratedFile, f: protogen.File) -> list[protogen.Message]:
    result: list[protogen.Message] = []
    for svc in f.services:
        for method in svc.methods:
            result.append(method.input)
            result.append(method.output)
    return result
