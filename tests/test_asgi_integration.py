"""Integration test for ConnectASGI server with real ASGI server."""

import asyncio
import threading
import time
from typing import TYPE_CHECKING

import aiohttp
import pytest
import uvicorn

from connectrpc.server import ClientRequest
from connectrpc.server import ServerResponse
from connectrpc.server_asgi import ConnectASGI
from tests.testing.testing_service_pb2 import EchoRequest
from tests.testing.testing_service_pb2 import EchoResponse

if TYPE_CHECKING:
    pass


class ASGITestServer:
    """Helper to run a real ASGI server for integration testing."""

    def __init__(self, app, host="127.0.0.1", port=8765):
        self.app = app
        self.host = host
        self.port = port
        self.server = None
        self.thread = None

    def start(self):
        """Start the server in a background thread."""
        config = uvicorn.Config(self.app, host=self.host, port=self.port, log_level="error")
        self.server = uvicorn.Server(config)

        def run_server():
            asyncio.new_event_loop().run_until_complete(self.server.serve())

        self.thread = threading.Thread(target=run_server, daemon=True)
        self.thread.start()

        # Wait for server to start
        timeout = 5
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Just check if the port is open by attempting to connect
                import socket

                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex((self.host, self.port))
                sock.close()
                if result == 0:
                    break
            except Exception:
                pass
            time.sleep(0.1)
        else:
            # Server didn't start, give it a bit more time
            time.sleep(0.5)

    def stop(self):
        """Stop the server."""
        if self.server:
            self.server.should_exit = True
        if self.thread:
            self.thread.join(timeout=1)

    @property
    def url(self):
        return f"http://{self.host}:{self.port}"


@pytest.fixture
def echo_app():
    """Create a test ASGI app with echo service."""
    app = ConnectASGI()

    async def echo_handler(req: ClientRequest[EchoRequest]) -> ServerResponse[EchoResponse]:
        response = EchoResponse()
        response.message = f"echo: {req.msg.message}"
        return ServerResponse(response)

    app.register_unary_rpc("/testing.TestingService/Echo", echo_handler, EchoRequest)
    return app


@pytest.fixture
def test_server(echo_app):
    """Create and start a test server."""
    server = ASGITestServer(echo_app)
    server.start()
    yield server
    server.stop()


@pytest.mark.asyncio
async def test_real_asgi_server_integration(test_server):
    """Test ConnectASGI with a real uvicorn server."""
    # Test successful RPC call
    async with (
        aiohttp.ClientSession() as session,
        session.post(
            f"{test_server.url}/testing.TestingService/Echo",
            headers={"content-type": "application/json"},
            json={"message": "hello world"},
            timeout=aiohttp.ClientTimeout(total=5),
        ) as response,
    ):
        assert response.status == 200
        assert response.headers["content-type"] == "application/json"

        result = await response.json()
        assert result["message"] == "echo: hello world"


@pytest.mark.asyncio
async def test_real_asgi_server_404(test_server):
    """Test 404 handling with real server."""
    async with (
        aiohttp.ClientSession() as session,
        session.post(
            f"{test_server.url}/unknown/path",
            headers={"content-type": "application/json"},
            json={"message": "test"},
            timeout=aiohttp.ClientTimeout(total=5),
        ) as response,
    ):
        assert response.status == 404


@pytest.mark.asyncio
async def test_real_asgi_server_405(test_server):
    """Test 405 handling with real server."""
    async with (
        aiohttp.ClientSession() as session,
        session.get(
            f"{test_server.url}/testing.TestingService/Echo", timeout=aiohttp.ClientTimeout(total=5)
        ) as response,
    ):
        assert response.status == 405
        assert "POST" in response.headers.get("allow", "")


@pytest.mark.asyncio
async def test_real_asgi_server_invalid_content_type(test_server):
    """Test 415 handling with real server."""
    async with (
        aiohttp.ClientSession() as session,
        session.post(
            f"{test_server.url}/testing.TestingService/Echo",
            headers={"content-type": "text/plain"},
            data="invalid data",
            timeout=aiohttp.ClientTimeout(total=5),
        ) as response,
    ):
        assert response.status == 415
