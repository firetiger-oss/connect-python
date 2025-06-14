import protogen


def generate(gen: protogen.Plugin) -> None:
    for f in gen.files_to_generate:
        g = gen.new_generated_file(
            f.proto.name.replace(".proto", "_pb2_connect.py"),
            f.py_import_path,
        )
        g.P("# Generated Connect client code")
        g.P()
        g.print_import()
        g.P()
        
        for s in f.services:
            g.P("class ", s.py_ident, "Client:")
            g.set_indent(4)
            g.P("def __init__(self, client):")
            g.set_indent(8)
            g.P("self._client = client")
            g.set_indent(4)
            g.P()
            
            for m in s.methods:
                g.P("def ", m.py_name, "(self, request):")
                g.set_indent(8)
                g.P("pass")
                g.set_indent(4)
            g.set_indent(0)
