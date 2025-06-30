from __future__ import annotations

import sys
from collections.abc import Iterable
from typing import TYPE_CHECKING

from multidict import CIMultiDict

from .errors import ConnectError

if TYPE_CHECKING:
    # wsgiref.types was added in Python 3.11.
    if sys.version_info >= (3, 11):
        from wsgiref.types import InputStream as WSGIInputStream
        from wsgiref.types import StartResponse
        from wsgiref.types import WSGIEnvironment
    else:
        from _typeshed.wsgi import InputStream as WSGIInputStream
        from _typeshed.wsgi import StartResponse
        from _typeshed.wsgi import WSGIEnvironment


class WSGIRequest:
    READ_CHUNK_SIZE = 8192

    def __init__(self, environ: WSGIEnvironment):
        self.environ = environ
        self.headers: CIMultiDict[str] = CIMultiDict()
        for k, v in environ.items():
            if k.startswith("HTTP_"):
                # Unfortunately, WSGI rewrites incoming HTTP request
                # headers, replacing '-' with '_'. It probably
                # replaces other characters too. This is a best guess
                # on what to do.
                header_key = k[5:].replace("_", "-")
                self.headers.add(header_key, v)

        self.method = str(environ["REQUEST_METHOD"])
        self.path = str(environ["PATH_INFO"])
        self.content_type = environ.get("CONTENT_TYPE", "").lower()
        self.content_length = int(environ.get("CONTENT_LENGTH", 0) or 0)
        self.input: WSGIInputStream = environ["wsgi.input"]


class WSGIResponse:
    """
    Lightweight wrapper to represent a WSGI HTTP response.
    """

    def __init__(self, start_response: StartResponse):
        self.start_response = start_response
        self.status_line = "200 OK"
        self.headers: CIMultiDict[str] = CIMultiDict()
        self.body: Iterable[bytes] = []

    def add_header(self, key: str, value: str) -> None:
        """
        Adds a header for key=value, appending to any existing header under that key.
        """
        self.headers.add(key, value)

    def set_header(self, key: str, value: str) -> None:
        """
        Set the header for key=value, overwriting any existing header under that key.
        """
        self.headers[key] = value

    def set_body(self, body: Iterable[bytes]) -> None:
        """
        Set the response body that will be sent.
        """
        self.body = body

    def set_status_line(self, status_line: str) -> None:
        """
        Set the HTTP Status-Line that will be set.
        """
        self.status_line = status_line

    def set_from_error(self, err: ConnectError) -> None:
        """
        Configure the WSGIResponse from a Connect error
        """
        self.set_status_line(err.code.http_status_line())
        body = err.to_json().encode()
        self.set_header("Content-Type", "application/json")
        self.set_header("Content-Encoding", "identity")
        self.set_header("Content-Length", str(len(body)))
        self.set_body([body])

    def send_headers(self) -> None:
        headers = []
        for k, v in self.headers.items():
            headers.append((str(k), str(v)))
        self.start_response(self.status_line, headers)

    def send(self) -> Iterable[bytes]:
        self.send_headers()
        return self.body
