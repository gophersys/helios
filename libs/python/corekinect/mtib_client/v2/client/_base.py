from typing import Iterator, Optional

import grpc

from protocols.mtib_v2.mtib_v2_pb2_grpc import MtibV2Stub

# Sentinel to distinguish "no timeout argument given" from explicit None.
# None means "no deadline" for gRPC (stream runs indefinitely).
_TIMEOUT_UNSET = object()


class BaseClient:
    """Base class providing shared gRPC call logic for all domain mixins.

    Subclasses access _stub and _timeout set by MtibV2Client.__init__.
    """

    _channel: Optional[grpc.Channel]
    _stub: Optional[MtibV2Stub]
    _timeout: float

    def _call(self, method_name: str, request, timeout: float = _TIMEOUT_UNSET):
        """Make a unary-unary gRPC call with error handling.

        Args:
            method_name: Name of the RPC method on the stub (e.g. 'HealthCheck').
            request: The protobuf request message.
            timeout: Override timeout in seconds. Omit to use client default.
                Pass None explicitly for no deadline.

        Returns:
            The protobuf response message.

        Raises:
            grpc.RpcError: On gRPC transport errors.
        """
        method = getattr(self._stub, method_name)
        effective_timeout = self._timeout if timeout is _TIMEOUT_UNSET else timeout
        return method(request, timeout=effective_timeout)

    def _server_stream(self, method_name: str, request, timeout: float = _TIMEOUT_UNSET) -> Iterator:
        """Make a unary-stream gRPC call.

        Args:
            method_name: Name of the server-streaming RPC method.
            request: The protobuf request message.
            timeout: Override timeout in seconds. Omit to use client default.
                Pass None explicitly for no deadline.

        Returns:
            Iterator of protobuf response messages.
        """
        method = getattr(self._stub, method_name)
        effective_timeout = self._timeout if timeout is _TIMEOUT_UNSET else timeout
        return method(request, timeout=effective_timeout)

    def _bidi_stream(self, method_name: str, request_iterator, timeout: float = _TIMEOUT_UNSET) -> Iterator:
        """Make a stream-stream (bidirectional) gRPC call.

        Args:
            method_name: Name of the bidirectional streaming RPC method.
            request_iterator: Iterator of protobuf request messages.
            timeout: Override timeout in seconds. Omit to use client default.
                Pass None explicitly for no deadline (required for persistent streams).

        Returns:
            Iterator of protobuf response messages.
        """
        method = getattr(self._stub, method_name)
        effective_timeout = self._timeout if timeout is _TIMEOUT_UNSET else timeout
        return method(request_iterator, timeout=effective_timeout)

    def _client_stream(self, method_name: str, request_iterator, timeout: float = _TIMEOUT_UNSET):
        """Make a stream-unary (client streaming) gRPC call.

        Args:
            method_name: Name of the client-streaming RPC method.
            request_iterator: Iterator of protobuf request messages.
            timeout: Override timeout in seconds. Omit to use client default.
                Pass None explicitly for no deadline.

        Returns:
            The protobuf response message.
        """
        method = getattr(self._stub, method_name)
        effective_timeout = self._timeout if timeout is _TIMEOUT_UNSET else timeout
        return method(request_iterator, timeout=effective_timeout)
