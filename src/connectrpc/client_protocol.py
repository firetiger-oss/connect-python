from enum import Enum


class ConnectProtocol(Enum):
    CONNECT_PROTOBUF = "connect-proto"
    CONNECT_JSON = "connect-json"
    GRPC = "grpc"
    GRPC_WEB = "grpc-web"
