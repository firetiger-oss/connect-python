from contextlib import contextmanager
from typing import BinaryIO

from google.protobuf.compiler.plugin_pb2 import CodeGeneratorRequest
from google.protobuf.compiler.plugin_pb2 import CodeGeneratorResponse
from google.protobuf.descriptor_pb2 import FileDescriptorProto
from google.protobuf.descriptor_pb2 import ServiceDescriptorProto


def invoke(input: BinaryIO, output: BinaryIO):
    req = CodeGeneratorRequest.FromString(input.read())

    resp = Invocation(req).run()

    output.write(resp.SerializeToString())
    output.flush()


class TypeRegistry:
    def __init__(self):
        self.messages = {}  # full_name -> (proto_file_name, simple_name)

    def register_file_messages(self, proto_file: FileDescriptorProto):
        """Register all messages from a proto file."""
        self._register_messages(proto_file, proto_file.message_type, proto_file.package)

    def _register_messages(self, proto_file: FileDescriptorProto, messages, parent_scope: str):
        for msg in messages:
            full_name = f"{parent_scope}.{msg.name}" if parent_scope else msg.name
            # Store proto file name and simple message name
            self.messages[full_name] = (proto_file.name, msg.name)
            # Register nested messages
            nested_scope = full_name
            self._register_messages(proto_file, msg.nested_type, nested_scope)

    def resolve_message_type(self, type_name: str) -> tuple[str, str]:
        """Resolve a message type name to (import_module, python_type_name).

        Args:
            type_name: Proto message type name (e.g., ".google.protobuf.Timestamp")

        Returns:
            Tuple of (import_module, python_type_name)
        """
        # Remove leading dot if present
        clean_name = type_name.lstrip(".")

        if clean_name in self.messages:
            proto_file_name, simple_name = self.messages[clean_name]
            # Convert proto file name to Python module name
            import_module = proto_file_name.replace(".proto", "_pb2")
            return import_module.replace("/", "."), simple_name
        else:
            # Fallback: extract simple name from full type name
            simple_name = clean_name.split(".")[-1]
            return "UNKNOWN_pb2", simple_name


class Invocation:
    def __init__(self, req: CodeGeneratorRequest):
        self.req = req
        self.type_registry = TypeRegistry()
        self.services = []

    def run(self) -> CodeGeneratorResponse:
        # First pass: register all message types
        for proto in self.req.proto_file:
            self.type_registry.register_file_messages(proto)

        # Second pass: generate services for files to generate
        files_to_generate = set(self.req.file_to_generate)
        for proto in self.req.proto_file:
            if proto.name in files_to_generate:
                self.handle_file(proto)

        # Create CodeGeneratorResponse
        response = CodeGeneratorResponse(
            supported_features=CodeGeneratorResponse.Feature.FEATURE_PROTO3_OPTIONAL,
        )

        # Group services by file and generate output files
        services_by_file = {}
        for service_client in self.services:
            file_key = service_client.source_file
            if file_key not in services_by_file:
                services_by_file[file_key] = []
            services_by_file[file_key].append(service_client)

        for source_file, service_clients in services_by_file.items():
            if len(service_clients) == 0:
                continue

            # Generate output filename
            output_filename = source_file.replace(".proto", "_pb2_connect.py")

            # Collect all imports from all services in this file
            all_imports = set()
            for service_client in service_clients:
                all_imports.update(service_client.imports)

            # Generate file content
            content_lines = []
            content_lines.append("# Generated Connect client code")
            content_lines.append("")

            # Add imports
            sorted_imports = sorted(all_imports, key=lambda x: (x.from_, x.ident))
            for imp in sorted_imports:
                content_lines.append(imp.to_import_statement())
            content_lines.append("")

            # Add service client classes
            for service_client in service_clients:
                content_lines.append(service_client.buf.content())
                content_lines.append("")

            # Create file response
            file_response = response.file.add()
            file_response.name = output_filename
            file_response.content = "\n".join(content_lines)

        return response

    def handle_file(self, proto_file: FileDescriptorProto):
        # Skip files with no services
        if len(proto_file.service) == 0:
            return

        for svc in proto_file.service:
            self.generate_service(svc, proto_file.package, proto_file.name)

    def generate_service(self, service: ServiceDescriptorProto, package: str, source_file: str):
        service_client = GeneratedServiceClient(service, package, self.type_registry)
        service_client.source_file = source_file
        service_client.generate_text()
        self.services.append(service_client)


class CodeBuilder:
    def __init__(self, indent: int = 0):
        self.indent_lvl = indent
        self.lines: list[str] = []

    def p(self, txt: str):
        self.lines.append(" " * self.indent_lvl + txt)

    @contextmanager
    def indent(self):
        self.indent_lvl += 4
        try:
            yield
        finally:
            self.indent_lvl -= 4

    def content(self) -> str:
        return "\n".join(self.lines)


# TODO: this is half baked:
class ImportedIdentifier:
    def __init__(self, from_: str, ident: str):
        self.from_ = from_
        self.ident = ident

    def to_import_statement(self) -> str:
        if self.ident == "":
            return f"import {self.from_}"
        return f"from {self.from_} import {self.ident}"


class GeneratedServiceClient:
    def __init__(
        self, proto: ServiceDescriptorProto, package_name: str, type_registry: TypeRegistry
    ):
        self.proto_def = proto
        self.package_name = package_name
        self.type_registry = type_registry
        self.buf = CodeBuilder()
        self.imports: set[ImportedIdentifier] = set()

    def name(self):
        return self.proto_def.name + "Client"

    def add_import(self, from_module: str, identifier: str):
        self.imports.add(ImportedIdentifier(from_module, identifier))

    def get_import_statements(self) -> list[str]:
        return [
            imp.to_import_statement()
            for imp in sorted(self.imports, key=lambda x: (x.from_, x.ident))
        ]

    def generate_text(self):
        # Add required imports
        self.add_import("collections.abc", "AsyncIterator")
        self.add_import("aiohttp", "")
        self.add_import("connectrpc.client", "ConnectClient")
        self.add_import("connectrpc.client", "ConnectProtocol")
        self.add_import("connectrpc.streams", "StreamInput")
        self.add_import("connectrpc.streams", "StreamOutput")

        # Generate class definition
        self.buf.p(f"class {self.name()}:")
        with self.buf.indent():
            self.generate_init()
            self.generate_methods()

    def generate_init(self):
        self.buf.p("def __init__(")
        self.buf.p("    self,")
        self.buf.p("    base_url: str,")
        self.buf.p("    http_client: aiohttp.ClientSession | None = None,")
        self.buf.p("    protocol: ConnectProtocol = ConnectProtocol.CONNECT_PROTOBUF,")
        self.buf.p("):")
        with self.buf.indent():
            self.buf.p("self.base_url = base_url")
            self.buf.p("self._connect_client = ConnectClient(http_client, protocol)")
        self.buf.p("")

    def generate_methods(self):
        for method in self.proto_def.method:
            if not method.client_streaming and not method.server_streaming:
                self.generate_unary_method(method)
            elif not method.client_streaming and method.server_streaming:
                self.generate_server_streaming_method(method)
            elif method.client_streaming and not method.server_streaming:
                self.generate_client_streaming_method(method)
            elif method.client_streaming and method.server_streaming:
                self.generate_bidirectional_streaming_method(method)

    def method_name(self, method):
        return method.name.lower()

    def service_path(self, method_name: str) -> str:
        return f"{self.package_name}.{self.proto_def.name}/{method_name}"

    def resolve_type(self, type_name: str) -> str:
        import_module, python_type = self.type_registry.resolve_message_type(type_name)
        self.add_import(import_module, python_type)
        return python_type

    def generate_unary_method(self, method):
        method_name = self.method_name(method)
        input_type = self.resolve_type(method.input_type)
        output_type = self.resolve_type(method.output_type)

        self.buf.p(f"async def {method_name}(self, req: {input_type}) -> {output_type}:")
        with self.buf.indent():
            self.buf.p(f'url = self.base_url + "/{self.service_path(method.name)}"')
            self.buf.p(f"return await self._connect_client.call_unary(url, req, {output_type})")
        self.buf.p("")

    def generate_server_streaming_method(self, method):
        method_name = self.method_name(method)
        input_type = self.resolve_type(method.input_type)
        output_type = self.resolve_type(method.output_type)

        # Simple iterator method
        self.buf.p(f"def {method_name}(")
        self.buf.p(f"    self, req: {input_type}")
        self.buf.p(f") -> AsyncIterator[{output_type}]:")
        with self.buf.indent():
            self.buf.p(f"return self._{method_name}_impl(req)")
        self.buf.p("")

        # Implementation helper
        self.buf.p(f"async def _{method_name}_impl(")
        self.buf.p(f"    self, req: {input_type}")
        self.buf.p(f") -> AsyncIterator[{output_type}]:")
        with self.buf.indent():
            self.buf.p(f"async with await self.{method_name}_stream(req) as stream:")
            with self.buf.indent():
                self.buf.p("async for response in stream:")
                with self.buf.indent():
                    self.buf.p("yield response")
        self.buf.p("")

        # Stream method for metadata access
        self.buf.p(f"async def {method_name}_stream(")
        self.buf.p(f"    self, req: {input_type}")
        self.buf.p(f") -> StreamOutput[{output_type}]:")
        with self.buf.indent():
            self.buf.p(f'url = self.base_url + "/{self.service_path(method.name)}"')
            self.buf.p("return await self._connect_client.call_server_streaming(")
            self.buf.p(f"    url, req, {output_type}")
            self.buf.p(")")
        self.buf.p("")

    def generate_client_streaming_method(self, method):
        method_name = self.method_name(method)
        input_type = self.resolve_type(method.input_type)
        output_type = self.resolve_type(method.output_type)

        self.buf.p(f"async def {method_name}(")
        self.buf.p(f"    self, reqs: StreamInput[{input_type}]")
        self.buf.p(f") -> {output_type}:")
        with self.buf.indent():
            self.buf.p(f'url = self.base_url + "/{self.service_path(method.name)}"')
            self.buf.p("return await self._connect_client.call_client_streaming(")
            self.buf.p(f"    url, reqs, {output_type}")
            self.buf.p(")")
        self.buf.p("")

    def generate_bidirectional_streaming_method(self, method):
        method_name = self.method_name(method)
        input_type = self.resolve_type(method.input_type)
        output_type = self.resolve_type(method.output_type)

        # Simple iterator method
        self.buf.p(f"def {method_name}(")
        self.buf.p(f"    self, reqs: StreamInput[{input_type}]")
        self.buf.p(f") -> AsyncIterator[{output_type}]:")
        with self.buf.indent():
            self.buf.p(f"return self._{method_name}_impl(reqs)")
        self.buf.p("")

        # Implementation helper
        self.buf.p(f"async def _{method_name}_impl(")
        self.buf.p(f"    self, reqs: StreamInput[{input_type}]")
        self.buf.p(f") -> AsyncIterator[{output_type}]:")
        with self.buf.indent():
            self.buf.p(f"async with await self.{method_name}_stream(reqs) as stream:")
            with self.buf.indent():
                self.buf.p("async for response in stream:")
                with self.buf.indent():
                    self.buf.p("yield response")
        self.buf.p("")

        # Stream method for metadata access
        self.buf.p(f"async def {method_name}_stream(")
        self.buf.p(f"    self, reqs: StreamInput[{input_type}]")
        self.buf.p(f") -> StreamOutput[{output_type}]:")
        with self.buf.indent():
            self.buf.p(f'url = self.base_url + "/{self.service_path(method.name)}"')
            self.buf.p("return await self._connect_client.call_bidirectional_streaming(")
            self.buf.p(f"    url, reqs, {output_type}")
            self.buf.p(")")
        self.buf.p("")
