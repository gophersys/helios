import re
import sys
from typing import Iterator, List, Optional

from smartcard.CardRequest import CardRequest
from smartcard.System import readers


class NfcReader:
    """Read NDEF Text ('T') records from NFC tags via a PC/SC reader.

    This class provides a generator-style `scan()` API that yields one processed
    text string for each NDEF "Text" record detected on a tapped NFC tag.
    Typical usage wraps the reader in a context manager to acquire the preferred
    PC/SC reader and then repeatedly waits for cards.

    The instance can optionally "emit" each scanned value to console, clipboard,
    keyboard, or a file; however, the primary use is to iterate over `scan()`
    and perform custom logic per yielded device ID.

    Args:
        prepend_0x: If True and a scanned text looks like a pure hex token
            (optionally already 0x-prefixed), normalize it to include a leading
            "0x" (e.g., "ABCDEF01" -> "0xABCDEF01").
        preferred_reader_substr: Case-insensitive substring used to select a
            specific reader from `smartcard.System.readers()` (e.g., "PICC"
            for ACR1252 contactless).
        keyboard_newline: When keyboard emission is enabled, append a newline
            after typing the string.
        console: If True, print each scanned text/device ID to stdout.
        clipboard: If True, copy each scanned text/device ID to the system
            clipboard (requires `pyperclip`).
        keyboard: If True, simulate typing each scanned text/device ID.
            Tries the `keyboard` package, then falls back to `pynput`.
        file_path: If set, append each scanned text/device ID to the file.

    Examples:
        >>> try:
        ...     with NfcReader(
        ...             prepend_0x=True,
        ...             console=False,
        ...             clipboard=False,
        ...             keyboard=False,
        ...             file_path="scanned_ids.txt",
        ...     ) as reader:
        ...         for device_id in reader.scan():
        ...             print(f"device_id: {device_id}")
        ...             test_verify_position_data(device_id)
        ... except KeyboardInterrupt:
        ...     pass

    Notes:
        - The generator `scan()` loops forever, yielding values whenever
          a tag is presented. Your code should decide when to break.
        - This reader extracts only NDEF "Text" (TNF=0x01, type="T") records.
    """

    class _NdefRecord:
        """Minimal container for a parsed NDEF record."""

        def __init__(self, tnf: int, record_type: bytes, payload: bytes) -> None:
            self.tnf = tnf
            self.record_type = record_type
            self.payload = payload

    # Matches a single hex token, with or without an existing 0x prefix.
    HEX_TOKEN_RE = re.compile(r"^(?:0x|0X)?[0-9A-Fa-f]+$")

    def __init__(
        self,
        *,
        prepend_0x: bool = False,
        preferred_reader_substr: str = "PICC",
        keyboard_newline: bool = True,
        console: bool = True,
        clipboard: bool = False,
        keyboard: bool = False,
        file_path: Optional[str] = None,
    ) -> None:
        # Configuration.
        self.prepend_0x = prepend_0x
        self.preferred_reader_substr = preferred_reader_substr
        self.keyboard_newline = keyboard_newline
        self.console = console
        self.clipboard = clipboard
        self.keyboard = keyboard
        self.file_path = file_path

        self._clipboard_available = False
        self._keyboard_backend: Optional[str] = None  # "keyboard" | "pynput" | None
        self._keyboard_driver = None

        # Clipboard output via pyperclip; if configured and if package installed.
        if self.clipboard:
            try:
                import pyperclip  # noqa: F401

                self._clipboard_available = True
            except Exception:
                print(
                    "[warn] Clipboard output requested but 'pyperclip' is not available.",
                    file=sys.stderr,
                )

        # Keyboard output using 'keyboard' or 'pynput'; if configured and if package(s) installed.
        if self.keyboard:
            try:
                import keyboard as keyboard_driver  # noqa: F401

                self._keyboard_backend = "keyboard"
                self._keyboard_driver = keyboard_driver
            except Exception:
                try:
                    from pynput.keyboard import Controller  # type: ignore

                    self._keyboard_backend = "pynput"
                    self._keyboard_driver = Controller()
                except Exception:
                    print(
                        "[warn] Keyboard output requested but neither 'keyboard' nor " "'pynput' is available.",
                        file=sys.stderr,
                    )
                    self._keyboard_backend = None

        # Assignment in __enter__
        self._selected_reader = None

    # ----------------------------------------  Context manager
    def __enter__(self) -> "NfcReader":
        """Acquire and announce the preferred PC/SC reader.

        Returns:
            NfcReader: The instance itself, so `as reader` binds to this object.
        """
        self._selected_reader = self._pick_smartcard_reader()
        print(f"Using reader: {self._selected_reader}")
        print("Tap a tag (Ctrl+C to quit).")
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        """No teardown required; allow exceptions to propagate.

        Returns:
            bool: False to signal that exceptions should not be suppressed.
        """
        return False

    # ----------------------------------------  Public APIs
    def scan(self) -> Iterator[str]:
        """Yield processed NDEF Text values as tags are scanned.

        This generator blocks waiting for a card, then parses the NDEF payload
        and yields each Text ('T') record found. Values are sanitized and may be
        0x-prefixed depending on configuration.

        Yields:
            str: The processed text/device ID for each Text record.

        Raises:
            KeyboardInterrupt: Propagated so callers can break cleanly.
        """
        # Allow use without `with`, but don't do that...
        if self._selected_reader is None:
            self._selected_reader = self._pick_smartcard_reader()
            print(f"Using reader: {self._selected_reader}")
            print("Tap a tag (Ctrl+C to quit).")

        while True:
            # Block until a *new* card is presented to the selected reader.
            card_request = CardRequest(
                timeout=None,
                readers=[self._selected_reader],
                newcardonly=True,
            )
            card_service = card_request.waitforcard()
            connection = card_service.connection

            try:
                # Establish APDU connection for this card.
                connection.connect()

                # Extract all NDEF Text values present on the tag.
                text_records = self._read_texts_from_tag(connection)

                # Yield each processed text string (often your device ID).
                for raw_text in text_records:
                    if not raw_text:
                        continue
                    sanitized_text = self._sanitize_text(raw_text)
                    maybe_prefixed = self._maybe_prefix_0x(sanitized_text)

                    # Emit to outputs and yield the processed value.
                    self._emit(maybe_prefixed)
                    yield maybe_prefixed

                # If no text records were present, loop and wait for another card.
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                print(f"(Error during card processing: {exc})")  # Keep scanning even if the card read fails.
            finally:
                try:
                    connection.disconnect()
                except Exception:
                    pass

    def run(self) -> None:
        """Consume `scan()` and emit results to configured outputs.

        This is a convenience loop for "fire-and-forget" behavior. Most callers
        will prefer iterating over `scan()` directly to run custom per-scan logic.
        """
        for scanned_text in self.scan():
            self._emit(scanned_text)

    # ----------------------------------------  Internals
    def _pick_smartcard_reader(self):
        """Select an available PC/SC reader.

        Preference is given to readers whose string representation contains
        `preferred_reader_substr` (case-insensitive). Otherwise, the first
        available reader is chosen.

        Returns:
            Any: A reader handle from `smartcard.System.readers()`.

        Raises:
            SystemExit: If no PC/SC readers are available.
        """
        available_readers = readers()
        if not available_readers:
            print("No PC/SC readers found.", file=sys.stderr)
            sys.exit(1)

        preferred_lower = self.preferred_reader_substr.lower()
        for reader_handle in available_readers:
            if preferred_lower in str(reader_handle).lower():
                return reader_handle

        # Fallback: choose the first enumerated reader.
        return available_readers[0]

    def _emit(self, text: str) -> None:
        """Emit a scanned value to configured outputs.

        Args:
            text: The processed text/device ID to emit.
        """
        # Console output.
        if self.console:
            print(text)

        # File output.
        if self.file_path:
            try:
                with open(self.file_path, "a", encoding="utf-8") as output_file:
                    output_file.write(text + "\n")
            except Exception as exc:
                print(f"[warn] File write failed: {exc}", file=sys.stderr)

        # Clipboard output via pyperclip.
        if self.clipboard and self._clipboard_available:
            try:
                import pyperclip

                pyperclip.copy(text)
            except Exception as exc:
                print(f"[warn] Clipboard copy failed: {exc}", file=sys.stderr)

        # Keyboard output via 'keyboard' or 'pynput'.
        if self.keyboard and self._keyboard_backend:
            try:
                if self._keyboard_backend == "keyboard":
                    # Directly "type" the string (and optional newline).
                    self._keyboard_driver.write(text + ("\n" if self.keyboard_newline else ""))
                elif self._keyboard_backend == "pynput":
                    from pynput.keyboard import Key

                    self._type_with_pynput(text)
                    if self.keyboard_newline:
                        self._keyboard_driver.press(Key.enter)
                        self._keyboard_driver.release(Key.enter)
            except Exception as exc:
                print(f"[warn] Keyboard typing failed: {exc}", file=sys.stderr)

    def _type_with_pynput(self, text: str) -> None:
        """Type characters using a `pynput` Controller (best-effort)."""
        for ch in text:
            self._keyboard_driver.type(ch)

    def _maybe_prefix_0x(self, value: str) -> str:
        """Normalize a hex token to have a '0x' prefix when configured.

        Args:
            value: Raw text parsed from the NDEF Text record.

        Returns:
            str: The normalized value (prefixed with "0x" if appropriate).
        """
        if not self.prepend_0x:
            return value
        if not self.HEX_TOKEN_RE.match(value):
            return value
        if value.startswith(("0x", "0X")):
            return value
        return "0x" + value

    @staticmethod
    def _sanitize_text(value: str) -> str:
        """Strip trailing NULs common in some encodings/storage."""
        return value.rstrip("\x00")

    # ----------------------------------------  NDEF helpers
    @staticmethod
    def _parse_ndef(message_bytes: bytes) -> List["_NdefRecord"]:
        """Parse an NDEF message into records (minimal TNF/Type/Payload support).

        Implements core parts of the NDEF record header parsing sufficient to
        extract payloads and types for typical Text records.

        Args:
            message_bytes: Raw NDEF message bytes.

        Returns:
            list[_NdefRecord]: Parsed NDEF records (minimal fields).
        """
        cursor = 0
        records: List[NfcReader._NdefRecord] = []

        while cursor < len(message_bytes):
            header = message_bytes[cursor]
            cursor += 1

            message_end = bool(header & 0x40)  # ME (Message End)
            short_record = bool(header & 0x10)  # SR (Short Record)
            id_length_present = bool(header & 0x08)  # IL (ID Length present)
            tnf = header & 0x07  # TNF (Type Name Format)

            # TYPE LENGTH (1 byte)
            if cursor >= len(message_bytes):
                break
            type_length = message_bytes[cursor]
            cursor += 1

            # PAYLOAD LENGTH (1 or 4 bytes depending on SR)
            if short_record:
                if cursor >= len(message_bytes):
                    break
                payload_length = message_bytes[cursor]
                cursor += 1
            else:
                if cursor + 4 > len(message_bytes):
                    break
                payload_length = int.from_bytes(message_bytes[cursor : cursor + 4], "big")
                cursor += 4

            # ID LENGTH (optional)
            id_length = message_bytes[cursor] if id_length_present else 0
            if id_length_present:
                cursor += 1

            # TYPE (type_length bytes)
            if cursor + type_length > len(message_bytes):
                break
            record_type = message_bytes[cursor : cursor + type_length]
            cursor += type_length

            # ID (skip id_length bytes if present)
            if id_length_present:
                if cursor + id_length > len(message_bytes):
                    break
                cursor += id_length

            # PAYLOAD (payload_length bytes)
            if cursor + payload_length > len(message_bytes):
                break
            payload = message_bytes[cursor : cursor + payload_length]
            cursor += payload_length

            records.append(NfcReader._NdefRecord(tnf, record_type, payload))
            if message_end:
                break

        return records

    @staticmethod
    def _extract_texts(records: List["_NdefRecord"]) -> List[str]:
        """Extract UTF-8/UTF-16 strings from Well-Known 'T' records.

        Args:
            records: Parsed NDEF records from `_parse_ndef`.

        Returns:
            list[str]: Text strings extracted from 'T' (Text) records.
        """
        texts: List[str] = []

        for record in records:
            # Well-Known Text ("T"), TNF = 0x01 per NFC Forum Text RTD.
            if record.tnf == 0x01 and record.record_type == b"T" and record.payload:
                status_byte = record.payload[0]
                language_code_length = status_byte & 0x3F
                is_utf16 = bool(status_byte & 0x80)

                # The payload is: [status][lang_code...][text...]
                raw_text_bytes = record.payload[1 + language_code_length :]

                try:
                    text_value = raw_text_bytes.decode("utf-16" if is_utf16 else "utf-8", errors="replace")
                except Exception:
                    # If decoding fails, skip this record (continue scanning others).
                    continue

                texts.append(text_value)

        return texts

    @staticmethod
    def _read_ndef_type2(connection) -> Optional[bytes]:
        """Read a Type 2 Tag user area and extract the NDEF TLV payload.

        This performs low-level READ commands across the typical user pages
        and parses TLVs to find the NDEF Message (Type 0x03).

        Args:
            connection: PC/SC connection for the active card.

        Returns:
            Optional[bytes]: Raw NDEF message if found, else None.
        """
        user_area = bytearray()

        # Type 2 user pages typically start at 0x04; read 4 bytes per page.
        for page_index in range(0x04, 0x50):
            data, sw1, sw2 = connection.transmit([0xFF, 0xB0, 0x00, page_index, 0x04])
            if (sw1, sw2) != (0x90, 0x00) or len(data) != 4:
                break
            user_area.extend(data)

        user_bytes = bytes(user_area)
        cursor = 0

        # Parse TLVs to locate NDEF (Type 0x03), with support for extended length.
        while cursor < len(user_bytes):
            tlv_type = user_bytes[cursor]
            cursor += 1

            if tlv_type == 0x00:  # NULL TLV
                continue
            if tlv_type == 0xFE:  # Terminator TLV
                break

            if cursor >= len(user_bytes):
                break
            length_byte = user_bytes[cursor]
            cursor += 1

            if length_byte == 0xFF:
                # Extended-length field (2 bytes)
                if cursor + 2 > len(user_bytes):
                    break
                tlv_length = int.from_bytes(user_bytes[cursor : cursor + 2], "big")
                cursor += 2
            else:
                tlv_length = length_byte

            if cursor + tlv_length > len(user_bytes):
                break

            if tlv_type == 0x03:  # NDEF Message TLV
                return user_bytes[cursor : cursor + tlv_length]

            cursor += tlv_length

        return None

    @staticmethod
    def _read_ndef_type4(connection) -> Optional[bytes]:
        """Select the NDEF app/file on a Type 4 Tag and read the NDEF bytes.

        Follows the NFC Forum Type 4 Tag procedure:
        - SELECT NDEF application
        - SELECT CC file (often E103)
        - READ CC, extract NDEF file FID
        - SELECT NDEF file
        - READ NLEN (first two bytes)
        - READ NLEN bytes starting at offset 2

        Args:
            connection: PC/SC connection for the active card.

        Returns:
            Optional[bytes]: Raw NDEF message if found, else None.
        """
        try:
            # SELECT NDEF application (AID: D2760000850101)
            AID_NDEF = [0xD2, 0x76, 0x00, 0x00, 0x85, 0x01, 0x01]
            _, sw1, sw2 = connection.transmit([0x00, 0xA4, 0x04, 0x00, len(AID_NDEF), *AID_NDEF, 0x00])
            if (sw1, sw2) != (0x90, 0x00):
                return None

            # SELECT Capability Container (commonly E103)
            _, sw1, sw2 = connection.transmit([0x00, 0xA4, 0x00, 0x0C, 0x02, 0xE1, 0x03])
            if (sw1, sw2) != (0x90, 0x00):
                return None

            # READ CC (need at least first 11 bytes to find the NDEF file FID)
            cc_bytes, sw1, sw2 = connection.transmit([0x00, 0xB0, 0x00, 0x00, 0x0F])
            if (sw1, sw2) != (0x90, 0x00) or len(cc_bytes) < 11:
                return None

            ndef_file_id = cc_bytes[9:11]
            if len(ndef_file_id) != 2:
                return None

            # SELECT the NDEF file via its FID.
            _, sw1, sw2 = connection.transmit([0x00, 0xA4, 0x00, 0x0C, 0x02, ndef_file_id[0], ndef_file_id[1]])
            if (sw1, sw2) != (0x90, 0x00):
                return None

            # READ NLEN (first two bytes of the NDEF file).
            nlen_bytes, sw1, sw2 = connection.transmit([0x00, 0xB0, 0x00, 0x00, 0x02])
            if (sw1, sw2) != (0x90, 0x00) or len(nlen_bytes) != 2:
                return None

            ndef_length = (nlen_bytes[0] << 8) | nlen_bytes[1]
            if ndef_length == 0:
                return b""

            # READ the NDEF payload starting at offset 2.
            result = bytearray()
            read_offset = 2
            remaining = ndef_length

            while remaining > 0:
                # Le capped to 255 per READ BINARY semantics.
                read_len = min(0xFF, remaining)
                chunk, sw1, sw2 = connection.transmit(
                    [
                        0x00,
                        0xB0,
                        (read_offset >> 8) & 0xFF,
                        read_offset & 0xFF,
                        read_len,
                    ]
                )
                if (sw1, sw2) != (0x90, 0x00) or not chunk:
                    return None

                result.extend(chunk)
                read_offset += len(chunk)
                remaining -= len(chunk)

            return bytes(result)

        except Exception:
            # On any transport/parsing error, treat as "not a Type 4 NDEF."
            return None

    def _read_texts_from_tag(self, connection) -> List[str]:
        """Try Type 2 first, then Type 4, and extract Text records.

        Args:
            connection: PC/SC connection for the active card.

        Returns:
            list[str]: Extracted text values. Empty if none found.
        """
        ndef_message = self._read_ndef_type2(connection)
        if ndef_message is None:
            ndef_message = self._read_ndef_type4(connection)
        if ndef_message is None:
            return []

        records = self._parse_ndef(ndef_message)
        return self._extract_texts(records)


if __name__ == "__main__":
    try:
        with NfcReader(
            prepend_0x=True,
            console=True,
            clipboard=False,
            keyboard=False,
            file_path=None,
        ) as reader:
            for device_id in reader.scan():
                print(f"Device ID: {device_id}")
    except KeyboardInterrupt:
        print("\nExiting NFC reader.")
        sys.exit(0)
