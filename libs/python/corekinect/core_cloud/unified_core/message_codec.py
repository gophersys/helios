"""
Binary message codec for serializing/deserializing dataclass messages.

This module provides a mixin class that adds binary packing and unpacking capabilities
to dataclass-based messages. It supports:
- Automatic binary serialization to bytes, hex, base64, and base10
- Struct-based packing with field validation
- Timestamp zeroing for configuration signatures
- Multiple encoding format caching
- Round-trip serialization/deserialization

Typical Usage:
    ```python
    @dataclass(frozen=True)
    class MyMessage(MessageCodec):
        uid: ClassVar[int] = 0x10
        message_id: int = 0x10
        message_length: int = 0
        timestamp: int = 0
        temperature: float = 0.0

        def pack_items(self) -> list[tuple[str, Any]]:
            return [
                ("B", self.message_id),
                ("H", 0),  # Placeholder for message_length
                ("I", self.timestamp),
                ("f", self.temperature),
            ]

        def timestamp_index(self) -> Optional[int]:
            return 2  # Index in pack_items where timestamp lives

    # Create and pack
    msg = MyMessage(temperature=25.5)
    msg.set_timestamp_now()
    msg.regen_encodings()

    # Access packed formats
    print(msg.hex_message)
    print(msg.base64_message)

    # Round-trip
    restored = MyMessage.from_base64(msg.base64_message)
    ```
"""

import base64
import struct
from dataclasses import fields
from datetime import datetime, timezone
from typing import ClassVar, Self, Type, Any, Optional

# Mapping from struct format codes to their byte sizes
# Only codes we support are included here
_STRUCT_CODE_TO_BYTE_SIZE = {
    "B": 1,  # unsigned char (0-255)
    "H": 2,  # unsigned short (0-65535)
    "I": 4,  # unsigned int (0-4294967295)
    "Q": 8,  # unsigned long long
    "b": 1,  # signed char (-128 to 127)
    "h": 2,  # signed short (-32768 to 32767)
    "i": 4,  # signed int (-2147483648 to 2147483647)
    "q": 8,  # signed long long
    "f": 4,  # float (32-bit IEEE 754)
    "d": 8,  # double (64-bit IEEE 754)
}


class MessageCodec:
    """
    Binary serialization mixin for dataclass-based messages.

    This mixin adds binary packing/unpacking capabilities to dataclasses that represent
    binary protocol messages. It uses Python's struct module for low-level byte operations
    and provides multiple output formats (bytes, hex, base64, base10).

    The codec expects messages to follow a header-body structure:
    - Header: Contains message_id (1 byte) and message_length (2 bytes unsigned)
    - Body: Remaining fields as defined by pack_items()

    Key Features:
        - Automatic message_length calculation
        - Optional timestamp zeroing for reproducible signatures
        - Range validation for integer fields
        - Cached encoding results to avoid repeated computation
        - Round-trip serialization support via from_base64()

    Subclass Requirements:
        Subclasses must implement pack_items() to define the binary layout:
        ```python
        def pack_items(self) -> list[tuple[str, Any]]:
            return [
                ("B", self.message_id),      # 1 byte: message type ID
                ("H", 0),                     # 2 bytes: length (auto-filled)
                ("I", self.timestamp),        # 4 bytes: Unix timestamp
                ("f", self.temperature),      # 4 bytes: float value
            ]
        ```

    Optional Overrides:
        - header_layout(): Define non-standard header field positions
        - timestamp_index(): Enable timestamp zeroing feature

    Attributes:
        uid (ClassVar[int]): Unique message type identifier for this message class.
        hex_message (str | None): Cached hex-encoded message with timestamp.
        base10_message (int | None): Cached base-10 integer representation.
        base64_message (str | None): Cached base64-encoded message.
        hex_message_no_timestamp (str | None): Cached hex with timestamp=0.
        base10_message_no_timestamp (int | None): Cached base-10 with timestamp=0.
        base64_message_no_timestamp (str | None): Cached base64 with timestamp=0.
    """

    # Class-level message identifier (subclasses should override)
    uid: ClassVar[int]

    # Cached encoded representations (populated by regen_encodings())
    hex_message: str | None = None
    base10_message: int | None = None
    base64_message: str | None = None
    hex_message_no_timestamp: str | None = None
    base10_message_no_timestamp: int | None = None
    base64_message_no_timestamp: str | None = None

    # Valid ranges for unsigned integer types
    _UNSIGNED_INT_RANGES = {
        "B": (0, 0xFF),  # 1 byte: 0-255
        "H": (0, 0xFFFF),  # 2 bytes: 0-65535
        "I": (0, 0xFFFFFFFF),  # 4 bytes: 0-4294967295
        "Q": (0, 0xFFFFFFFFFFFFFFFF),  # 8 bytes: 0-18446744073709551615
    }

    # Valid ranges for signed integer types
    _SIGNED_INT_RANGES = {
        "b": (-0x80, 0x7F),  # 1 byte: -128 to 127
        "h": (-0x8000, 0x7FFF),  # 2 bytes: -32768 to 32767
        "i": (-0x80000000, 0x7FFFFFFF),  # 4 bytes: -2147483648 to 2147483647
        "q": (-0x8000000000000000, 0x7FFFFFFFFFFFFFFF),  # 8 bytes: large signed range
    }

    # Floating point type codes
    _FLOATING_POINT_CODES = {"f", "d"}

    # ========== Subclass Hooks (Must Override) ==========

    def pack_items(self) -> list[tuple[str, Any]]:
        """
        Define the binary layout of this message as a list of (struct_code, value) tuples.

        This is the primary method subclasses must implement. It specifies both the
        structure and the data for binary packing. The struct codes follow Python's
        struct module format.

        Returns:
            List of tuples where each tuple contains:
            - str: struct format code (e.g., "B", "H", "I", "f", "d")
            - Any: value to pack for that field

        Example:
            ```python
            def pack_items(self) -> list[tuple[str, Any]]:
                return [
                    ("B", self.message_id),        # 1 byte unsigned: message type
                    ("H", 0),                       # 2 bytes unsigned: length (auto-filled)
                    ("I", self.timestamp),          # 4 bytes unsigned: Unix timestamp
                    ("H", self.interval_minutes),   # 2 bytes unsigned: config value
                    ("B", self.threshold),          # 1 byte unsigned: threshold
                    ("f", self.temperature),        # 4 bytes float: sensor reading
                ]
            ```

        Important Notes:
            - The second tuple (index 1) should be ("H", 0) for message_length
            - message_length will be automatically calculated and filled
            - Use big-endian byte order (struct format prefix ">" is added automatically)
            - Only codes defined in _STRUCT_CODE_TO_BYTE_SIZE are supported

        Raises:
            NotImplementedError: This method must be overridden by subclasses.
        """
        raise NotImplementedError(
            f"{type(self).__name__}.pack_items() must be implemented by subclass. "
            f"Return a list of (struct_code, value) tuples defining the binary layout."
        )

    # ========== Optional Subclass Hooks ==========

    def header_layout(self) -> tuple[int, int]:
        """
        Specify the positions of message_id and message_length in pack_items().

        The default implementation assumes standard header layout:
        - Index 0: message_id (1 byte "B")
        - Index 1: message_length (2 bytes "H")

        Override this method if your message uses a different header structure.

        Returns:
            Tuple of (id_index, length_index) specifying where in pack_items()
            the message ID and length fields are located.

        Example (Custom Header):
            ```python
            def header_layout(self) -> tuple[int, int]:
                # Custom header with length first, then ID
                return (1, 0)  # ID at index 1, length at index 0
            ```

        Default:
            (0, 1) - Standard header: ID first, then length
        """
        return (0, 1)

    def timestamp_index(self) -> Optional[int]:
        """
        Specify the position of the timestamp field in pack_items() for zeroing support.

        If your message contains a timestamp field and you want to support zero-timestamp
        packing (for configuration signatures or templates), return the index where the
        timestamp appears in the pack_items() list.

        Zero-timestamp packing is useful for:
        - Creating configuration signatures that don't depend on send time
        - Template messages for comparison
        - Message deduplication

        Returns:
            Index of timestamp field in pack_items(), or None to disable this feature.

        Example:
            ```python
            def pack_items(self):
                return [
                    ("B", self.message_id),
                    ("H", 0),
                    ("I", self.timestamp),  # <- This is at index 2
                    ("f", self.temperature),
                ]

            def timestamp_index(self) -> Optional[int]:
                return 2  # Enable zero-timestamp packing for this field
            ```

        Default:
            None - Timestamp zeroing is disabled by default
        """
        return None

    # ========== Public API Methods ==========

    def set_timestamp_now(self) -> Self:
        """
        Set the timestamp field to the current UTC time (if this message has a timestamp).

        This is a convenience method for messages that have a 'timestamp' attribute.
        It sets the timestamp to the current Unix epoch time in seconds.

        Returns:
            Self for method chaining.

        Example:
            ```python
            msg = MyMessage(temperature=25.5)
            msg.set_timestamp_now().regen_encodings()
            print(f"Message sent at: {datetime.fromtimestamp(msg.timestamp, tz=timezone.utc)}")
            ```

        Note:
            This method only works if the dataclass has a 'timestamp' attribute.
            If the attribute doesn't exist, this method does nothing.
        """
        if hasattr(self, "timestamp"):
            # Use object.__setattr__ to work with frozen dataclasses
            object.__setattr__(self, "timestamp", int(datetime.now(timezone.utc).timestamp()))
        return self

    def regen_encodings(self) -> None:
        """
        Generate and cache all encoded representations of this message.

        This method performs binary packing and stores the results in multiple formats:
        - hex_message: Hexadecimal string
        - base10_message: Integer representation
        - base64_message: Base64-encoded string

        If timestamp_index() is configured, also generates zero-timestamp versions:
        - hex_message_no_timestamp
        - base10_message_no_timestamp
        - base64_message_no_timestamp

        This method should be called after message construction and before accessing
        the cached encoding attributes.

        Example:
            ```python
            msg = MyMessage(temperature=25.5)
            msg.set_timestamp_now()
            msg.regen_encodings()  # Generate all cached formats

            # Now access cached encodings
            print(f"Hex: {msg.hex_message}")
            print(f"Base64: {msg.base64_message}")
            print(f"Base10: {msg.base10_message}")

            # For config signatures (timestamp=0)
            print(f"Signature: {msg.hex_message_no_timestamp}")
            ```

        Performance Note:
            Encodings are only cached, not automatically updated. If you modify
            message fields after calling regen_encodings(), you must call it
            again to update the cached values.
        """
        # Pack with actual timestamp and cache results
        packed_with_timestamp = self._pack(zero_timestamp=False)
        self._cache_encoded_formats(packed_with_timestamp, is_zero_timestamp=False)

        # If timestamp zeroing is supported, pack and cache that version too
        timestamp_field_index = self.timestamp_index()
        if timestamp_field_index is not None:
            packed_without_timestamp = self._pack(zero_timestamp=True)
            self._cache_encoded_formats(packed_without_timestamp, is_zero_timestamp=True)

    def pack_to_bytes(self, *, zero_timestamp: bool = False) -> bytes:
        """
        Pack this message into a binary byte string.

        Args:
            zero_timestamp: If True and timestamp_index() is configured, the timestamp
                          field will be set to 0 in the output. This is useful for
                          creating reproducible configuration signatures.

        Returns:
            Binary byte string in big-endian format.

        Example:
            ```python
            msg = MyMessage(temperature=25.5)
            msg.set_timestamp_now()

            # Normal packing with timestamp
            binary_data = msg.pack_to_bytes()

            # Packing for signature (timestamp=0)
            signature_data = msg.pack_to_bytes(zero_timestamp=True)
            ```

        Raises:
            ValueError: If field values are out of range or message structure is invalid.
        """
        return self._pack(zero_timestamp=zero_timestamp)

    def pack_to_base64(self, *, zero_timestamp: bool = False) -> str:
        """
        Pack this message into a base64-encoded string.

        This is the most compact text representation and is commonly used for
        API payloads, database storage, and JSON serialization.

        Args:
            zero_timestamp: If True and timestamp_index() is configured, the timestamp
                          field will be set to 0 in the output.

        Returns:
            Base64-encoded string representation of the packed message.

        Example:
            ```python
            msg = GroundModeConfigV2(
                gps_heartbeat_period_minutes=60,
                motion_acceleration_threshold=29
            )

            # Send via API
            payload = msg.pack_to_base64()
            # Result: "NgAVAAAAAAA8AAA8PAAdAgMKHjwAAAAA"

            # For signature verification
            sig = msg.pack_to_base64(zero_timestamp=True)
            ```

        Raises:
            ValueError: If field values are out of range or message structure is invalid.
        """
        packed_bytes = self._pack(zero_timestamp=zero_timestamp)
        return base64.b64encode(packed_bytes).decode("utf-8")

    @classmethod
    def from_base64(cls: Type[Self], encoded_string: str) -> Self:
        """
        Deserialize a message from a base64-encoded string.

        This method performs the reverse operation of pack_to_base64(), converting
        a base64 string back into a message instance. It decodes the base64, unpacks
        the binary data using struct, and constructs a new instance.

        Args:
            encoded_string: Base64-encoded message string from pack_to_base64().

        Returns:
            New instance of this message class with fields populated from the binary data.

        Raises:
            ValueError: If the base64 string is invalid or the binary data doesn't
                       match the expected format.
            struct.error: If unpacking fails due to size mismatch.

        Example:
            ```python
            # Round-trip serialization
            original = GroundModeConfigV2(
                gps_heartbeat_period_minutes=60,
                motion_acceleration_threshold=29
            )

            # Serialize
            encoded = original.pack_to_base64()

            # Deserialize
            restored = GroundModeConfigV2.from_base64(encoded)

            assert restored.gps_heartbeat_period_minutes == 60
            assert restored.motion_acceleration_threshold == 29
            ```

        Note:
            This is a basic implementation that works for simple messages.
            Subclasses may need to override this for complex field mapping.
        """
        # Decode base64 to binary
        binary_payload = base64.b64decode(encoded_string)

        # Create an empty instance (bypasses __init__)
        instance = object.__new__(cls)
        cls._initialize_default_field_values(instance)

        # Get the binary layout from this class
        field_layout = instance.pack_items()
        struct_format = ">" + "".join(format_code for format_code, _ in field_layout)

        # Unpack binary data
        try:
            unpacked_values = struct.unpack(struct_format, binary_payload)
        except struct.error as error:
            raise ValueError(
                f"{cls.__name__}: Failed to unpack binary data. "
                f"Expected format '{struct_format}' but got {len(binary_payload)} bytes. "
                f"Error: {error}"
            ) from error

        # Store unpacked values back into instance attributes
        # This is a simplified approach - subclasses should override for proper mapping
        for (format_code, _), unpacked_value in zip(field_layout, unpacked_values):
            # Try to set message_length if it exists
            if format_code == "H" and hasattr(instance, "message_length"):
                object.__setattr__(instance, "message_length", int(unpacked_value))

        # Cache the encoding
        instance._cache_encoded_formats(binary_payload, is_zero_timestamp=False)
        return instance

    # ========== Internal Implementation Methods ==========

    @classmethod
    def _initialize_default_field_values(cls, instance: Any) -> None:
        """
        Initialize all dataclass fields to their default values or None.

        This is used by from_base64() to create an empty instance before
        populating it with unpacked data.

        Args:
            instance: Newly created instance (from object.__new__) to initialize.
        """
        for field in fields(cls):
            if not hasattr(instance, field.name):
                # Set to default if available, otherwise None
                default_value = field.default if field.default is not field.default_factory else None
                object.__setattr__(instance, field.name, default_value)

    def _pack(self, *, zero_timestamp: bool) -> bytes:
        """
        Internal method to pack the message into binary format.

        This method:
        1. Retrieves the field layout from pack_items()
        2. Calculates message_length based on body size
        3. Optionally zeros the timestamp field
        4. Validates all field values are within range
        5. Packs using struct in big-endian format

        Args:
            zero_timestamp: Whether to set timestamp field to 0.

        Returns:
            Packed binary data as bytes.

        Raises:
            ValueError: If pack_items() returns invalid data, header indices are wrong,
                       field values are out of range, or struct codes are unsupported.
        """
        # Get the list of fields to pack
        fields_to_pack = list(self.pack_items())
        if not fields_to_pack:
            raise ValueError(f"{type(self).__name__}: pack_items() returned an empty list")

        # Determine header field positions
        message_id_index, message_length_index = self.header_layout()
        if not (0 <= message_id_index < len(fields_to_pack) and 0 <= message_length_index < len(fields_to_pack)):
            raise ValueError(
                f"{type(self).__name__}: Invalid header layout indices "
                f"({message_id_index}, {message_length_index}). "
                f"Must be within range [0, {len(fields_to_pack)})"
            )

        # Calculate message_length (sum of body field sizes after header)
        header_end_index = max(message_id_index, message_length_index)
        body_size_bytes = 0

        for field_index, (struct_code, _) in enumerate(fields_to_pack):
            # Validate struct code is supported
            field_size_bytes = _STRUCT_CODE_TO_BYTE_SIZE.get(struct_code)
            if field_size_bytes is None:
                raise ValueError(
                    f"{type(self).__name__}: Unsupported struct code '{struct_code}' at index {field_index}. "
                    f"Supported codes: {list(_STRUCT_CODE_TO_BYTE_SIZE.keys())}"
                )

            # Add to body size if this field is after the header
            if field_index > header_end_index:
                body_size_bytes += field_size_bytes

        # Validate body size fits in unsigned short (2 bytes)
        length_code, _ = fields_to_pack[message_length_index]
        if length_code != "H":
            raise ValueError(
                f"{type(self).__name__}: message_length field must use 'H' (unsigned short), "
                f"but got '{length_code}' at index {message_length_index}"
            )
        if not (0 <= body_size_bytes <= 0xFFFF):
            raise ValueError(
                f"{type(self).__name__}: Calculated body size {body_size_bytes} bytes "
                f"exceeds maximum for 'H' type (65535 bytes)"
            )

        # Update message_length field
        fields_to_pack[message_length_index] = (length_code, body_size_bytes)

        # Apply timestamp zeroing if requested
        timestamp_field_index = self.timestamp_index()
        if zero_timestamp and timestamp_field_index is not None:
            timestamp_code, _ = fields_to_pack[timestamp_field_index]
            fields_to_pack[timestamp_field_index] = (timestamp_code, 0)

        # Build struct format string (big-endian)
        struct_format = ">" + "".join(format_code for format_code, _ in fields_to_pack)

        # Validate and collect values for packing
        values_to_pack: list[int | float] = []

        for field_index, (format_code, field_value) in enumerate(fields_to_pack):
            # Check for None values
            if field_value is None:
                raise ValueError(
                    f"{type(self).__name__}: Field at index {field_index} ('{format_code}') "
                    f"has None value. All fields must have values for packing."
                )

            # Validate unsigned integer ranges
            if format_code in self._UNSIGNED_INT_RANGES:
                min_value, max_value = self._UNSIGNED_INT_RANGES[format_code]
                int_value = int(field_value)
                if not (min_value <= int_value <= max_value):
                    raise ValueError(
                        f"{type(self).__name__}: Field at index {field_index} ('{format_code}') "
                        f"value {int_value} is out of range [{min_value}, {max_value}]"
                    )
                values_to_pack.append(int_value)

            # Validate signed integer ranges
            elif format_code in self._SIGNED_INT_RANGES:
                min_value, max_value = self._SIGNED_INT_RANGES[format_code]
                int_value = int(field_value)
                if not (min_value <= int_value <= max_value):
                    raise ValueError(
                        f"{type(self).__name__}: Field at index {field_index} ('{format_code}') "
                        f"value {int_value} is out of range [{min_value}, {max_value}]"
                    )
                values_to_pack.append(int_value)

            # Validate floating point types
            elif format_code in self._FLOATING_POINT_CODES:
                if not isinstance(field_value, (int, float)):
                    raise ValueError(
                        f"{type(self).__name__}: Field at index {field_index} ('{format_code}') "
                        f"expected numeric type but got {type(field_value).__name__}"
                    )
                values_to_pack.append(float(field_value))

            else:
                raise ValueError(
                    f"{type(self).__name__}: Unsupported struct code '{format_code}' at index {field_index}"
                )

        # Pack into binary format
        try:
            return struct.pack(struct_format, *values_to_pack)
        except struct.error as error:
            raise ValueError(
                f"{type(self).__name__}: struct.pack failed with format '{struct_format}'. " f"Error: {error}"
            ) from error

    def _cache_encoded_formats(self, packed_bytes: bytes, *, is_zero_timestamp: bool) -> None:
        """
        Cache multiple encoded representations of the packed message.

        Args:
            packed_bytes: Binary message data to encode.
            is_zero_timestamp: If True, cache to *_no_timestamp attributes.
                              If False, cache to regular attributes.

        Encodings Generated:
            - Hexadecimal string (lowercase)
            - Base-10 integer (big-endian interpretation)
            - Base64 string (standard encoding)
        """
        # Generate hex encoding
        hex_encoded = packed_bytes.hex()

        # Generate base-10 integer representation
        base10_encoded = int(hex_encoded, 16)

        # Generate base64 encoding
        base64_encoded = base64.b64encode(packed_bytes).decode("utf-8")

        # Cache to appropriate attributes based on timestamp flag
        if is_zero_timestamp:
            object.__setattr__(self, "hex_message_no_timestamp", hex_encoded)
            object.__setattr__(self, "base10_message_no_timestamp", base10_encoded)
            object.__setattr__(self, "base64_message_no_timestamp", base64_encoded)
        else:
            object.__setattr__(self, "hex_message", hex_encoded)
            object.__setattr__(self, "base10_message", base10_encoded)
            object.__setattr__(self, "base64_message", base64_encoded)
