import protogen

# Universal arguments on all RPC methods
common_params = [
    "extra_headers: HeaderInput | None=None",
    "timeout_seconds: float | None=None",
]

common_params_str = ", ".join(common_params)

common_args = [
    "extra_headers",
    "timeout_seconds",
]
common_args_str = ", ".join(common_args)


def docstring(g: protogen.GeneratedFile, *args: str) -> None:
    g.P('"""', *args, '"""')


def _generate_unary_rpc(
    g: protogen.GeneratedFile, f: protogen.File, s: protogen.Service, m: protogen.Method
) -> None:
    """Generate a unary RPC method."""
    g.P("async def call_", m.py_name, "(")
    g.P("    self, req: ", m.input.py_ident, ",", common_params_str)
    g.P(") -> UnaryOutput[", m.output.py_ident, "]:")
    g.set_indent(8)
    docstring(
        g, "Low-level method to call ", m.proto.name, ", granting access to errors and metadata"
    )
    g.P('url = self.base_url + "/', f.proto.package, ".", s.proto.name, "/", m.proto.name, '"')
    g.P(
        "return await self._connect_client.call_unary(url, req, ",
        m.output.py_ident,
        ",",
        common_args_str,
        ")",
    )
    g.set_indent(4)
    g.P()
    g.P("async def ", m.py_name, "(")
    g.P("    self, req: ", m.input.py_ident, ",", common_params_str)
    g.P(") -> ", m.output.py_ident, ":")
    g.set_indent(8)
    g.P("response = await self.call_", m.py_name, "(req, ", common_args_str, ")")
    g.P("err = response.error()")
    g.P("if err is not None:")
    g.P("    raise err")
    g.P("msg = response.message()")
    g.P("if msg is None:")
    g.P("    raise ConnectProtocolError('missing response message')")
    g.P("return msg")
    g.set_indent(4)
    g.P()


def _generate_server_streaming_rpc(
    g: protogen.GeneratedFile, f: protogen.File, s: protogen.Service, m: protogen.Method
) -> None:
    """Generate a server streaming RPC with dual API pattern."""
    # Simple iterator method
    g.P("def ", m.py_name, "(")
    g.P("    self, req: ", m.input.py_ident, ",", common_params_str)
    g.P(") -> AsyncIterator[", m.output.py_ident, "]:")
    g.P("    return self._", m.py_name, "_iterator(req, ", common_args_str, ")")
    g.P()

    # Implementation helper
    g.P("async def _", m.py_name, "_iterator(")
    g.P("    self, req: ", m.input.py_ident, ",", common_params_str)
    g.P(") -> AsyncIterator[", m.output.py_ident, "]:")
    g.P("    stream_output = await self.call_", m.py_name, "(req, extra_headers)")
    g.P("    err = stream_output.error()")
    g.P("    if err is not None:")
    g.P("        raise err")
    g.P("    async with stream_output as stream:")
    g.P("        async for response in stream:")
    g.P("            yield response")
    g.P()

    g.P("async def call_", m.py_name, "(")
    g.P("    self, req: ", m.input.py_ident, ",", common_params_str)
    g.P(") -> StreamOutput[", m.output.py_ident, "]:")
    g.set_indent(8)
    docstring(
        g, "Low-level method to call ", m.proto.name, ", granting access to errors and metadata"
    )
    g.set_indent(4)
    g.P('    url = self.base_url + "/', f.proto.package, ".", s.proto.name, "/", m.proto.name, '"')
    g.P("    return await self._connect_client.call_server_streaming(")
    g.P("        url, req, ", m.output.py_ident, ", ", common_args_str)
    g.P("    )")
    g.P()


def _generate_client_streaming_rpc(
    g: protogen.GeneratedFile, f: protogen.File, s: protogen.Service, m: protogen.Method
) -> None:
    """Generate a client streaming RPC method."""
    g.P("async def call_", m.py_name, "(")
    g.P("    self, reqs: StreamInput[", m.input.py_ident, "], ", common_params_str)
    g.P(") -> StreamOutput[", m.output.py_ident, "]:")
    g.set_indent(8)
    docstring(
        g, "Low-level method to call ", m.proto.name, ", granting access to errors and metadata"
    )
    g.set_indent(4)
    g.P('    url = self.base_url + "/', f.proto.package, ".", s.proto.name, "/", m.proto.name, '"')
    g.P("    return await self._connect_client.call_client_streaming(")
    g.P("        url, reqs, ", m.output.py_ident, ", ", common_args_str)
    g.P("    )")
    g.P()

    g.P("async def ", m.py_name, "(")
    g.P("    self, reqs: StreamInput[", m.input.py_ident, "], ", common_params_str)
    g.P(") -> ", m.output.py_ident, ":")
    g.P("    stream_output = await self.call_", m.py_name, "(reqs, extra_headers)")
    g.P("    err = stream_output.error()")
    g.P("    if err is not None:")
    g.P("        raise err")
    g.P("    async with stream_output as stream:")
    g.P("        async for response in stream:")
    g.P("            return response")
    g.P("    raise ConnectProtocolError('no response message received')")
    g.P()


def _generate_bidirectional_streaming_rpc(
    g: protogen.GeneratedFile, f: protogen.File, s: protogen.Service, m: protogen.Method
) -> None:
    """Generate a bidirectional streaming RPC with dual API pattern."""
    # Simple iterator method
    g.P("def ", m.py_name, "(")
    g.P("    self, reqs: StreamInput[", m.input.py_ident, "], ", common_params_str)
    g.P(") -> AsyncIterator[", m.output.py_ident, "]:")
    g.P("    return self._", m.py_name, "_iterator(reqs, ", common_args_str, ")")
    g.P()

    # Implementation helper
    g.P("async def _", m.py_name, "_iterator(")
    g.P("    self, reqs: StreamInput[", m.input.py_ident, "], ", common_params_str)
    g.P(") -> AsyncIterator[", m.output.py_ident, "]:")
    g.P("    stream_output = await self.call_", m.py_name, "(reqs, ", common_args_str, ")")
    g.P("    err = stream_output.error()")
    g.P("    if err is not None:")
    g.P("        raise err")
    g.P("    async with stream_output as stream:")
    g.P("        async for response in stream:")
    g.P("            yield response")
    g.P()

    # Stream method for metadata access
    g.P("async def call_", m.py_name, "(")
    g.P(
        "    self, reqs: StreamInput[",
        m.input.py_ident,
        "], ",
        common_params_str,
    )
    g.P(") -> StreamOutput[", m.output.py_ident, "]:")
    g.set_indent(8)
    docstring(
        g, "Low-level method to call ", m.proto.name, ", granting access to errors and metadata"
    )
    g.set_indent(4)
    g.P('    url = self.base_url + "/', f.proto.package, ".", s.proto.name, "/", m.proto.name, '"')
    g.P("    return await self._connect_client.call_bidirectional_streaming(")
    g.P("        url, reqs, ", m.output.py_ident, ", ", common_args_str)
    g.P("    )")
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
        g.P("from connectrpc.client_connect import ConnectProtocolError")
        g.P("from connectrpc.headers import HeaderInput")
        g.P("from connectrpc.streams import StreamInput")
        g.P("from connectrpc.streams import StreamOutput")
        g.P("from connectrpc.unary import UnaryOutput")
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
            assert method.input is not None
            assert method.output is not None
            result.append(method.input)
            result.append(method.output)
    return result
