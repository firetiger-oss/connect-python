"""Connect Protocol error handling.

This module implements the Connect Protocol error specification, including
error codes, HTTP status mappings, and JSON error parsing.
"""

import base64
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any
from typing import Optional

from google.protobuf.message import Message
from google.protobuf.symbol_database import Default as DefaultSymbolDatabase
from google.protobuf.symbol_database import SymbolDatabase


class ConnectErrorCode(Enum):
    """Connect Protocol error codes with their HTTP status mappings."""

    CANCELED = ("canceled", 499)
    UNKNOWN = ("unknown", 500)
    INVALID_ARGUMENT = ("invalid_argument", 400)
    DEADLINE_EXCEEDED = ("deadline_exceeded", 504)
    NOT_FOUND = ("not_found", 404)
    ALREADY_EXISTS = ("already_exists", 409)
    PERMISSION_DENIED = ("permission_denied", 403)
    RESOURCE_EXHAUSTED = ("resource_exhausted", 429)
    FAILED_PRECONDITION = ("failed_precondition", 400)
    ABORTED = ("aborted", 409)
    OUT_OF_RANGE = ("out_of_range", 400)
    UNIMPLEMENTED = ("unimplemented", 501)
    INTERNAL = ("internal", 500)
    UNAVAILABLE = ("unavailable", 503)
    DATA_LOSS = ("data_loss", 500)
    UNAUTHENTICATED = ("unauthenticated", 401)

    def __init__(self, code_name: str, http_status: int):
        self.code_name = code_name
        self.http_status = http_status

    @classmethod
    def from_code_name(cls, code_name: str) -> Optional["ConnectErrorCode"]:
        """Get ConnectErrorCode from string code name."""
        for code in cls:
            if code.code_name == code_name:
                return code
        return None

    @classmethod
    def from_http_status(cls, http_status: int) -> Optional["ConnectErrorCode"]:
        """Get ConnectErrorCode from HTTP status code."""
        for code in cls:
            if code.http_status == http_status:
                return code
        return None


# HTTP status to Connect error code fallback mapping
# Used when no explicit Connect error code is provided
HTTP_TO_CONNECT_FALLBACK = {
    400: ConnectErrorCode.INTERNAL,
    401: ConnectErrorCode.UNAUTHENTICATED,
    403: ConnectErrorCode.PERMISSION_DENIED,
    404: ConnectErrorCode.UNIMPLEMENTED,
    429: ConnectErrorCode.UNAVAILABLE,
    502: ConnectErrorCode.UNAVAILABLE,
    503: ConnectErrorCode.UNAVAILABLE,
    504: ConnectErrorCode.UNAVAILABLE,
}


def infer_connect_code_from_http_status(http_status: int) -> ConnectErrorCode:
    """Infer Connect error code from HTTP status when no explicit code is provided."""
    # Use the inference mapping table (not direct ConnectErrorCode mapping)
    # This follows the Connect spec's HTTP-to-Connect error code mapping
    if http_status in HTTP_TO_CONNECT_FALLBACK:
        return HTTP_TO_CONNECT_FALLBACK[http_status]

    # Default to unknown for all other status codes
    return ConnectErrorCode.UNKNOWN


@dataclass
class ConnectErrorDetail:
    type: str
    value: str
    debug: Any | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConnectErrorDetail":
        return ConnectErrorDetail(
            type=data["type"],
            value=data["value"],
            debug=data.get("debug"),
        )

    def to_dict(self) -> dict[str, Any]:
        v = {
            "type": self.type,
            "value": self.value,
        }
        if self.debug is not None:
            v["debug"] = self.debug
        return v

    def message(self, symbol_db: SymbolDatabase | None = None) -> Message:
        """Deserialize the error detail into a richer representation.

        The error detail's type is taken as a fully qualified protobuf
        symbol. The value is taken as the base64-encoded binary
        representation of that symbol's value.

        """
        if symbol_db is None:
            symbol_db = DefaultSymbolDatabase()
        msg_type = symbol_db.GetSymbol(self.type)
        msg_val = msg_type()

        # Add '==' to ensure the value is padded
        data = base64.b64decode(self.value + "==")
        msg_val.ParseFromString(data)

        return msg_val


class ConnectError(Exception):
    """Represents a Connect Protocol error.

    Connect errors are sent as JSON responses with non-200 HTTP status codes.
    They contain at minimum a code and message, and may include additional details.
    """

    def __init__(
        self,
        code: ConnectErrorCode,
        message: str,
        details: list[ConnectErrorDetail] | None = None,
        http_status: int | None = None,
    ):
        """Initialize a ConnectError.

        Args:
            code: The Connect error code
            message: Human-readable error message
            details: Optional additional error details
            http_status: HTTP status code (defaults to code's standard mapping)
        """
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or []
        self.http_status = http_status or code.http_status

    def to_json(self) -> str:
        """Serialize error to JSON format per Connect specification."""
        error_dict = self.to_dict()
        return json.dumps(error_dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary representation."""
        result: dict[str, Any] = {
            "code": self.code.code_name,
            "message": self.message,
        }
        if self.details:
            result["details"] = [detail.to_dict() for detail in self.details]
        return result

    @classmethod
    def from_json(cls, json_str: str, http_status: int | None = None) -> "ConnectError":
        """Parse ConnectError from JSON response.

        Args:
            json_str: JSON error response
            http_status: HTTP status code from response

        Returns:
            ConnectError instance

        Raises:
            ValueError: If JSON is malformed or missing required fields
        """
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in error response: {e}") from e

        return cls.from_dict(data, http_status)

    @classmethod
    def from_dict(cls, data: dict[str, Any], http_status: int | None = None) -> "ConnectError":
        """Parse ConnectError from dictionary.

        Args:
            data: Error data dictionary
            http_status: HTTP status code from response

        Returns:
            ConnectError instance

        Raises:
            ValueError: If required fields are missing
        """
        if not isinstance(data, dict):
            return ConnectError(
                ConnectErrorCode.UNKNOWN,
                "invalid error response received",
            )

        code_name = data.get("code")
        message = data.get("message", "")

        # Parse the Connect error code
        code = ConnectErrorCode.from_code_name(code_name) if code_name else None
        if not code:
            code = infer_connect_code_from_http_status(http_status or 500)

        # Extract additional details (everything except code/message)
        details = data.get("details", [])
        details = [ConnectErrorDetail.from_dict(d) for d in details]

        return cls(code, message, details, http_status)

    @classmethod
    def from_http_response(
        cls, http_status: int, content: str | bytes | None = None
    ) -> "ConnectError":
        """Create ConnectError from HTTP response.

        Args:
            http_status: HTTP status code
            content: Response body content (JSON error if present)

        Returns:
            ConnectError instance with inferred or explicit error code
        """
        # Handle empty content
        if not content:
            code = infer_connect_code_from_http_status(http_status)
            return cls(code, f"HTTP {http_status}", http_status=http_status)

        # Normalize content to string
        if isinstance(content, bytes):
            try:
                content = content.decode("utf-8")
            except UnicodeDecodeError:
                code = infer_connect_code_from_http_status(http_status)
                return cls(
                    code, f"HTTP {http_status}: Invalid UTF-8 content", http_status=http_status
                )

        # Try to parse as JSON error
        if content.strip():
            try:
                return cls.from_json(content, http_status)
            except (ValueError, json.JSONDecodeError):
                # Malformed JSON, fall back to HTTP status inference
                pass

        # Fall back to HTTP status code inference
        code = infer_connect_code_from_http_status(http_status)
        message = f"HTTP {http_status}" + (f": {content}" if content else "")
        return cls(code, message, http_status=http_status)

    def __str__(self) -> str:
        return f"[{self.code.code_name}] {self.message}"

    def __repr__(self) -> str:
        return f"ConnectError(code={self.code.code_name!r}, message={self.message!r})"
