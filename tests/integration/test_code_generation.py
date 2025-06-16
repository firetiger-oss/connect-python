"""Integration tests for the Connect Python code generator."""

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


class CodeGeneratorTester:
    """Helper class for testing code generation end-to-end."""

    def __init__(self, temp_dir: Path, proto_files_dir: Path):
        self.temp_dir = temp_dir
        self.proto_files_dir = proto_files_dir

    def run_protoc(
        self, proto_files: list[str], extra_args: list[str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        """Run protoc with the connect_python plugin on the given proto files."""
        if extra_args is None:
            extra_args = []

        # Copy proto files to temp directory to handle imports properly
        proto_paths = []
        for proto_file in proto_files:
            src = self.proto_files_dir / proto_file
            dst = self.temp_dir / proto_file
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(src.read_text())
            proto_paths.append(str(dst))

        cmd = [
            "protoc",
            f"--proto_path={self.temp_dir}",
            f"--python_out={self.temp_dir}",
            f"--pyi_out={self.temp_dir}",
            f"--connect_python_out={self.temp_dir}",
            *extra_args,
            *proto_paths,
        ]

        return subprocess.run(cmd, capture_output=True, text=True, cwd=self.temp_dir)

    def verify_no_errors(
        self, result: subprocess.CompletedProcess[str], proto_files: list[str]
    ) -> None:
        """Verify that protoc ran without errors."""
        if result.returncode != 0:
            pytest.fail(
                f"protoc failed for {proto_files}:\n"
                f"STDOUT: {result.stdout}\n"
                f"STDERR: {result.stderr}\n"
                f"Command: {' '.join(result.args) if hasattr(result, 'args') else 'N/A'}"
            )

    def get_generated_files(self, proto_file: str) -> dict[str, Path]:
        """Get the paths to generated files for a given proto file."""
        base_name = proto_file.replace(".proto", "")
        return {
            "pb2": self.temp_dir / f"{base_name}_pb2.py",
            "connect": self.temp_dir / f"{base_name}_pb2_connect.py",
        }

    def verify_files_generated(self, proto_file: str) -> dict[str, Path]:
        """Verify that the expected files were generated."""
        files = self.get_generated_files(proto_file)

        for file_type, file_path in files.items():
            if not file_path.exists():
                pytest.fail(f"Expected {file_type} file not generated: {file_path}")

        return files

    def verify_importable(self, file_path: Path) -> None:
        """Verify that a Python file can be imported without syntax errors."""
        # Add the temp directory to Python path for imports
        sys.path.insert(0, str(self.temp_dir))

        try:
            # Load the module dynamically
            spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
            if spec is None or spec.loader is None:
                pytest.fail(f"Could not create module spec for {file_path}")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

        except Exception as e:
            pytest.fail(f"Failed to import {file_path}: {e}")
        finally:
            # Clean up Python path
            if str(self.temp_dir) in sys.path:
                sys.path.remove(str(self.temp_dir))

    def run_mypy_check(self, file_path: Path) -> subprocess.CompletedProcess[str]:
        """Run mypy type checking on a generated file."""
        # Create a temporary mypy config that includes our temp directory
        mypy_config = self.temp_dir / "mypy.ini"
        mypy_config.write_text(f"""
[mypy]
python_version = 3.10
strict = false
check_untyped_defs = false
disallow_untyped_calls = false
warn_return_any = false
ignore_missing_imports = true
mypy_path = {self.temp_dir}
""")

        cmd = [sys.executable, "-m", "mypy", "--config-file", str(mypy_config), str(file_path)]

        return subprocess.run(cmd, capture_output=True, text=True)

    def verify_type_checking(self, file_path: Path) -> None:
        """Verify that a generated file passes mypy type checking."""
        result = self.run_mypy_check(file_path)

        if result.returncode != 0:
            pytest.fail(
                f"mypy type checking failed for {file_path}:\n"
                f"STDOUT: {result.stdout}\n"
                f"STDERR: {result.stderr}"
            )


@pytest.fixture
def generator_tester(temp_generated_dir: Path, proto_files_dir: Path) -> CodeGeneratorTester:
    """Create a CodeGeneratorTester instance."""
    return CodeGeneratorTester(temp_generated_dir, proto_files_dir)


def test_empty_service_generation(generator_tester: CodeGeneratorTester) -> None:
    """Test generation for proto file with no services."""
    proto_files = ["empty_service.proto"]

    # Run protoc
    result = generator_tester.run_protoc(proto_files)
    generator_tester.verify_no_errors(result, proto_files)

    # Verify files were generated
    files = generator_tester.verify_files_generated("empty_service")

    # pb2 file should exist and be importable
    generator_tester.verify_importable(files["pb2"])

    # Connect file should be empty or minimal since no services
    connect_content = files["connect"].read_text()
    assert "class" not in connect_content or connect_content.count("class") == 0, (
        "Connect file should not contain service classes when no services are defined"
    )


def test_multiple_services_generation(generator_tester: CodeGeneratorTester) -> None:
    """Test generation for proto file with multiple services."""
    proto_files = ["multiple_services.proto"]

    # Run protoc
    result = generator_tester.run_protoc(proto_files)
    generator_tester.verify_no_errors(result, proto_files)

    # Verify files were generated
    files = generator_tester.verify_files_generated("multiple_services")

    # Both files should be importable
    generator_tester.verify_importable(files["pb2"])
    generator_tester.verify_importable(files["connect"])

    # Verify type checking passes
    generator_tester.verify_type_checking(files["connect"])

    # Connect file should contain both service classes
    connect_content = files["connect"].read_text()
    assert "class FirstServiceClient:" in connect_content
    assert "class SecondServiceClient:" in connect_content


def test_client_streaming_generation(generator_tester: CodeGeneratorTester) -> None:
    """Test generation for client streaming RPC patterns."""
    proto_files = ["client_streaming.proto"]

    # Run protoc
    result = generator_tester.run_protoc(proto_files)
    generator_tester.verify_no_errors(result, proto_files)

    # Verify files were generated
    files = generator_tester.verify_files_generated("client_streaming")

    # Both files should be importable
    generator_tester.verify_importable(files["pb2"])
    generator_tester.verify_importable(files["connect"])

    # Verify type checking passes
    generator_tester.verify_type_checking(files["connect"])

    # Verify client streaming method is generated correctly
    connect_content = files["connect"].read_text()
    assert "async def aggregate_data(" in connect_content
    assert "StreamInput[client_streaming_pb2.StreamRequest]" in connect_content
    assert "call_client_streaming" in connect_content


def test_imported_messages_generation(generator_tester: CodeGeneratorTester) -> None:
    """Test generation with imported message types."""
    # Need to generate both files for imports to work
    proto_files = ["imported_messages.proto", "main_service.proto"]

    # Run protoc
    result = generator_tester.run_protoc(proto_files)
    generator_tester.verify_no_errors(result, proto_files)

    # Verify files were generated for both
    imported_files = generator_tester.verify_files_generated("imported_messages")
    main_files = generator_tester.verify_files_generated("main_service")

    # All files should be importable
    generator_tester.verify_importable(imported_files["pb2"])
    generator_tester.verify_importable(main_files["pb2"])
    generator_tester.verify_importable(main_files["connect"])

    # Verify type checking passes
    generator_tester.verify_type_checking(main_files["connect"])

    # Verify that imported types are used correctly
    connect_content = main_files["connect"].read_text()
    assert "main_service_pb2.ServiceRequest" in connect_content
    assert "main_service_pb2.ServiceResponse" in connect_content


def test_complex_types_generation(generator_tester: CodeGeneratorTester) -> None:
    """Test generation with complex message types."""
    proto_files = ["complex_types.proto"]

    # Run protoc
    result = generator_tester.run_protoc(proto_files)
    generator_tester.verify_no_errors(result, proto_files)

    # Verify files were generated
    files = generator_tester.verify_files_generated("complex_types")

    # Both files should be importable
    generator_tester.verify_importable(files["pb2"])
    generator_tester.verify_importable(files["connect"])

    # Verify type checking passes
    generator_tester.verify_type_checking(files["connect"])

    # Verify both unary and bidirectional streaming methods
    connect_content = files["connect"].read_text()
    assert "async def process_complex(" in connect_content
    assert "def stream_complex(" in connect_content
    assert "StreamInput[complex_types_pb2.ComplexRequest]" in connect_content
    assert "AsyncIterator[complex_types_pb2.ComplexResponse]" in connect_content


def test_generation_with_extra_args(generator_tester: CodeGeneratorTester) -> None:
    """Test that code generation works with additional protoc arguments."""
    proto_files = ["multiple_services.proto"]

    # Test with extra arguments (this tests the framework's extensibility)
    extra_args = ["--experimental_allow_proto3_optional"]

    # Run protoc with extra args
    result = generator_tester.run_protoc(proto_files, extra_args)
    generator_tester.verify_no_errors(result, proto_files)

    # Verify files were generated and are valid
    files = generator_tester.verify_files_generated("multiple_services")
    generator_tester.verify_importable(files["pb2"])
    generator_tester.verify_importable(files["connect"])


def test_error_handling_invalid_proto() -> None:
    """Test that the framework properly handles invalid proto input."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create an invalid proto file
        invalid_proto = temp_path / "invalid.proto"
        invalid_proto.write_text("this is not valid protobuf syntax")

        # Run protoc and expect it to fail
        cmd = [
            "protoc",
            f"--proto_path={temp_path}",
            f"--python_out={temp_path}",
            f"--pyi_out={temp_path}",
            f"--connect_python_out={temp_path}",
            str(invalid_proto),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        # Should fail with non-zero exit code
        assert result.returncode != 0, "protoc should fail with invalid proto syntax"
        assert (
            "expected top-level statement" in result.stderr.lower()
            or "syntax error" in result.stderr.lower()
            or "parse error" in result.stderr.lower()
        )
