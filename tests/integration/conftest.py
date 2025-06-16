"""Pytest configuration for integration tests."""

import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def temp_generated_dir() -> Iterator[Path]:
    """Create a temporary directory for generated files that gets cleaned up."""
    temp_dir = tempfile.mkdtemp(prefix="connect_python_generated_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def proto_files_dir() -> Path:
    """Return the directory containing test .proto files."""
    return Path(__file__).parent / "proto_files"
