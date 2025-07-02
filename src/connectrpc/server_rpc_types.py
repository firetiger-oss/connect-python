from enum import Enum


class RPCType(Enum):
    UNARY = 1
    CLIENT_STREAMING = 2
    SERVER_STREAMING = 3
    BIDI_STREAMING = 4
