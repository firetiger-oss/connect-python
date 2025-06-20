"""Header utilities for Connect RPC client.

Provides type-safe handling of HTTP headers with support for multi-valued headers
while maintaining backward compatibility with simple dict usage.
"""

from __future__ import annotations

from multidict import CIMultiDict
from multidict import MultiDict
from urllib3 import HTTPHeaderDict

# Type definitions for header inputs - what users can pass
HeaderInput = (
    dict[str, str]  # Simple dict (most common case)
    | dict[str, list[str]]  # Multi-valued dict
    | CIMultiDict[str]  # Full multidict support
    | MultiDict[str]
    | HTTPHeaderDict
)

# Internal type used throughout the client stack
HeadersInternal = CIMultiDict[str]


def normalize_headers(input_headers: HeaderInput | None) -> HeadersInternal:
    """Convert any header input format to CIMultiDict.

    Args:
        input_headers: Headers in any supported format, or None

    Returns:
        CIMultiDict containing the normalized headers
    """
    if input_headers is None:
        return CIMultiDict()

    if isinstance(input_headers, CIMultiDict):
        return CIMultiDict(input_headers)

    if isinstance(input_headers, MultiDict):
        return CIMultiDict(input_headers)

    result: CIMultiDict[str] = CIMultiDict()

    if isinstance(input_headers, dict):
        for key, value in input_headers.items():
            if isinstance(value, list):
                # Multi-valued dict format
                for v in value:
                    result.add(key, v)
            else:
                # Simple dict format
                result.add(key, value)
        return result

    if isinstance(input_headers, HTTPHeaderDict):
        for k, v in input_headers.iteritems():
            result.add(k, v)
        return result

    raise TypeError(f"Unsupported header type: {type(input_headers)}")


def merge_headers(base: HeadersInternal, extra: HeaderInput | None) -> HeadersInternal:
    """Merge extra headers into base headers, preserving multi-values.

    Args:
        base: Base headers (CIMultiDict)
        extra: Additional headers to merge in any supported format

    Returns:
        New CIMultiDict with merged headers
    """
    result = CIMultiDict(base)  # Start with copy of base

    if extra is None:
        return result

    extra_normalized = normalize_headers(extra)

    # Add all values from extra headers
    for key, value in extra_normalized.items():
        result.add(key, value)

    return result


def headers_to_dict(headers: HeadersInternal) -> dict[str, str]:
    """Convert CIMultiDict to simple dict for backward compatibility.

    For headers with multiple values, only the last value is kept.
    This is for compatibility with code that expects dict[str, str].

    Args:
        headers: CIMultiDict headers

    Returns:
        Simple dict with single values per key
    """
    return dict(headers)


def multidict_to_urllib3(headers: HeadersInternal) -> HTTPHeaderDict:
    result = HTTPHeaderDict()
    for k, v in headers.items():
        result.add(k, v)
    return result


def get_all_header_values(headers: HeadersInternal, key: str) -> list[str]:
    """Get all values for a header key.

    Args:
        headers: CIMultiDict headers
        key: Header name (case-insensitive)

    Returns:
        List of all values for the key, empty list if key not found
    """
    return headers.getall(key, [])
