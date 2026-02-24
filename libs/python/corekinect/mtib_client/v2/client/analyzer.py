from typing import Iterator, List, Optional, Tuple

from protocols.mtib_v2.mtib_v2_pb2 import (
    AddDecoderRequest,
    GetDecodedDataRequest,
    I2cDecoderConfig,
    AnalyzerCaptureConfig,
    AnalyzerCaptureStartRequest,
    AnalyzerCaptureStatusRequest,
    AnalyzerCaptureStopRequest,
    AnalyzerChannelConfig,
    ListAnalyzerProvidersRequest,
    Protocol,
    SpiDecoderConfig,
)

from ._base import BaseClient


class AnalyzerProviderInfo:
    """Information about an available logic analyzer provider.

    Attributes:
        name: Provider identifier (e.g., "saleae", "sigrok", "simulation")
        display_name: Human-readable name (e.g., "Saleae Logic 2")
        available: Whether provider is currently available
        max_sample_rate_hz: Maximum supported sample rate
        max_channels: Maximum number of channels
        supported_protocols: List of supported protocol decoder names
        supports_streaming: Whether real-time streaming is supported
        supports_triggers: Whether hardware triggers are supported
        hardware_detected: Detected hardware (e.g., "Logic 8", "fx2lafw")
        supported_export_formats: Supported export formats (e.g., ["csv", "vcd"])
    """

    def __init__(
        self,
        name: str = "",
        display_name: str = "",
        available: bool = False,
        max_sample_rate_hz: int = 0,
        max_channels: int = 0,
        supported_protocols: List[str] = None,
        supports_streaming: bool = False,
        supports_triggers: bool = False,
        hardware_detected: str = "",
        supported_export_formats: List[str] = None,
    ):
        self.name = name
        self.display_name = display_name
        self.available = available
        self.max_sample_rate_hz = max_sample_rate_hz
        self.max_channels = max_channels
        self.supported_protocols = supported_protocols or []
        self.supports_streaming = supports_streaming
        self.supports_triggers = supports_triggers
        self.hardware_detected = hardware_detected
        self.supported_export_formats = supported_export_formats or []


class AnalyzerMixin(BaseClient):
    """Digital signal analyzer (logic analyzer) operations.

    Provides vendor-neutral access to logic analyzer functionality.
    Supports multiple backends: Saleae Logic 2, sigrok, and simulation.
    """

    def analyzer_list_providers(self) -> Tuple[Optional[str], List[AnalyzerProviderInfo]]:
        """List available logic analyzer providers.

        Queries the server to discover which logic analyzer backends are
        available (e.g., Saleae, sigrok, simulation) and their capabilities.

        Returns:
            (error, providers) tuple. error is None on success.
            providers is a list of AnalyzerProviderInfo objects.

        Example:
            ```python
            err, providers = client.analyzer_list_providers()
            if not err:
                for p in providers:
                    print(f"{p.display_name}: {p.max_sample_rate_hz} Hz")
            ```

        Note:
            This method requires the updated protocol with ListAnalyzerProviders RPC.
            Will return error if server doesn't support it yet.
        """
        try:
            from protocols.mtib_v2.mtib_v2_pb2 import ListAnalyzerProvidersRequest
            resp = self._call("ListAnalyzerProviders", ListAnalyzerProvidersRequest())
            if not resp.success:
                return resp.message, []
            providers = [
                AnalyzerProviderInfo(
                    name=p.name,
                    display_name=p.display_name,
                    available=p.available,
                    max_sample_rate_hz=p.max_sample_rate_hz,
                    max_channels=p.max_channels,
                    supported_protocols=list(p.supported_protocols),
                    supports_streaming=p.supports_streaming,
                    supports_triggers=p.supports_triggers,
                    hardware_detected=p.hardware_detected,
                    supported_export_formats=list(p.supported_export_formats),
                )
                for p in resp.providers
            ]
            return None, providers
        except Exception as e:
            return f"analyzer_list_providers error: {e}", []

    def analyzer_capture_start(
        self,
        channels: List[int],
        sample_rate_hz: int = 10_000_000,
        duration_s: float = 1.0,
        prefer_provider: str = "auto",
        max_memory_mb: int = 512,
        trigger_channel: Optional[int] = None,
        trigger_edge: str = "rising",
        pre_trigger_s: float = 0.0,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Start a logic analyzer capture.

        Starts capturing digital signals on the specified channels using
        any available logic analyzer backend.

        Args:
            channels: List of digital channel numbers to capture (e.g., [0, 1, 2, 3])
            sample_rate_hz: Sample rate in Hz (default 10 MHz)
            duration_s: Capture duration in seconds (default 1.0)
            prefer_provider: Preferred provider ("auto", "saleae", "sigrok", "simulation")
            max_memory_mb: Memory limit in MB (default 512)
            trigger_channel: Optional channel for trigger (None = no trigger)
            trigger_edge: Trigger edge type ("rising", "falling", "either")
            pre_trigger_s: Pre-trigger capture duration in seconds

        Returns:
            (error, capture_id) tuple. error is None on success.
            capture_id is used to query status and retrieve data.

        Example:
            ```python
            err, cap_id = client.analyzer_capture_start(
                channels=[0, 1, 2, 3],
                sample_rate_hz=10_000_000,
                duration_s=5.0,
            )
            if not err:
                print(f"Capture started: {cap_id}")
            ```
        """
        try:
            # Build channel configs
            channel_configs = [
                AnalyzerChannelConfig(
                    channel=ch,
                    label=f"CH{ch}",
                    enabled=True,
                )
                for ch in channels
            ]

            # Build trigger config
            trigger_enabled = trigger_channel is not None
            trigger_edge_enum = {
                "rising": 0,   # TRIGGER_RISING
                "falling": 1,  # TRIGGER_FALLING
                "either": 2,   # TRIGGER_EITHER
            }.get(trigger_edge.lower(), 0)

            config = AnalyzerCaptureConfig(
                channels=channel_configs,
                sample_rate_hz=sample_rate_hz,
                duration_s=duration_s,
                trigger_enabled=trigger_enabled,
                trigger_channel=trigger_channel or 0,
                trigger_edge=trigger_edge_enum,
                pre_trigger_s=pre_trigger_s,
            )

            # TODO: Add prefer_provider and max_memory_mb once protocol updated
            # For now, use existing AnalyzerCaptureStart
            resp = self._call("AnalyzerCaptureStart", AnalyzerCaptureStartRequest(config=config))

            if not resp.success:
                return resp.message, None
            return None, resp.capture_id

        except Exception as e:
            return f"analyzer_capture_start error: {e}", None

    def analyzer_stream(
        self,
        capture_id: str,
        max_samples_per_chunk: int = 1000,
    ) -> Iterator:
        """Stream samples in real-time from an active capture.

        Returns an iterator that yields sample chunks as they're captured.
        Useful for live monitoring of digital signals.

        Args:
            capture_id: Capture ID from analyzer_capture_start
            max_samples_per_chunk: Maximum samples per yielded chunk (default 1000)

        Yields:
            AnalyzerStreamResponse objects containing sample data.

        Example:
            ```python
            err, cap_id = client.analyzer_capture_start(...)
            if not err:
                for chunk in client.analyzer_stream(cap_id):
                    print(f"Received {len(chunk.samples)} samples")
                    if chunk.capture_complete:
                        break
            ```

        Note:
            This method requires the updated protocol with AnalyzerStream RPC.
            Will raise exception if server doesn't support it yet.
        """
        try:
            # TODO: Implement once AnalyzerStreamRequest is in protocol
            # from protocols.mtib_v2.mtib_v2_pb2 import AnalyzerStreamRequest
            # request = AnalyzerStreamRequest(
            #     capture_id=capture_id,
            #     max_samples_per_chunk=max_samples_per_chunk,
            #     interval_s=0.1,
            # )
            # for response in self._server_stream("AnalyzerStream", request, timeout=None):
            #     yield response
            #     if response.capture_complete:
            #         break

            raise NotImplementedError("AnalyzerStream not yet implemented in protocol")

        except Exception as e:
            self.logger.error(f"analyzer_stream error: {e}")
            raise

    def analyzer_capture_status(
        self, capture_id: str
    ) -> Tuple[Optional[str], Optional[dict]]:
        """Get the status of an analyzer capture.

        Queries the current state of a capture: waiting for trigger, capturing,
        complete, or error.

        Args:
            capture_id: Capture ID from analyzer_capture_start

        Returns:
            (error, status_info) tuple. error is None on success.
            status_info dict contains:
                - status: int (0=WAITING_TRIGGER, 1=CAPTURING, 2=COMPLETE, 3=ERROR)
                - progress: float (0.0 to 1.0)
                - samples_captured: int (total samples captured)
                - samples_dropped: int (samples dropped due to memory limit)
                - memory_usage_mb: float (current memory usage)

        Example:
            ```python
            err, status = client.analyzer_capture_status(cap_id)
            if not err:
                if status["status"] == 2:  # COMPLETE
                    print("Capture complete!")
            ```
        """
        try:
            resp = self._call(
                "AnalyzerCaptureStatus",
                AnalyzerCaptureStatusRequest(capture_id=capture_id)
            )

            if not resp.success:
                return resp.message, None

            status_info = {
                "status": resp.status,
                "progress": resp.progress,
                # New fields (will be 0 until protocol updated):
                "samples_captured": getattr(resp, "samples_captured", 0),
                "samples_dropped": getattr(resp, "samples_dropped", 0),
                "memory_usage_mb": getattr(resp, "memory_usage_mb", 0.0),
            }

            return None, status_info

        except Exception as e:
            return f"analyzer_capture_status error: {e}", None

    def analyzer_capture_stop(self, capture_id: str) -> Optional[str]:
        """Stop an analyzer capture.

        Stops an active capture before it completes naturally.
        Captured data remains available for export and decoding.

        Args:
            capture_id: Capture ID from analyzer_capture_start

        Returns:
            Error message string, or None on success.

        Example:
            ```python
            err = client.analyzer_capture_stop(cap_id)
            if not err:
                print("Capture stopped")
            ```
        """
        try:
            resp = self._call(
                "AnalyzerCaptureStop",
                AnalyzerCaptureStopRequest(capture_id=capture_id)
            )

            if not resp.success:
                return resp.message
            return None

        except Exception as e:
            return f"analyzer_capture_stop error: {e}"

    def analyzer_export(
        self,
        capture_id: str,
        format: str = "csv",
        output_path: str = "capture.csv"
    ) -> Tuple[Optional[str], Optional[str]]:
        """Export analyzer capture to file.

        Exports captured data to various formats for offline analysis.

        Args:
            capture_id: Capture ID from analyzer_capture_start
            format: Export format ("csv", "vcd", "native_saleae", "native_sigrok")
            output_path: Filename (relative to server export directory)

        Returns:
            (error, file_path) tuple. error is None on success.
            file_path is the full path to the exported file.

        Example:
            ```python
            err, path = client.analyzer_export(cap_id, format="csv")
            if not err:
                print(f"Exported to: {path}")
            ```

        Note:
            This method requires the updated protocol with AnalyzerExport RPC.
            Will return error if server doesn't support it yet.
        """
        try:
            # TODO: Implement once AnalyzerExportRequest is in protocol
            # from protocols.mtib_v2.mtib_v2_pb2 import AnalyzerExportRequest
            # format_enum = {
            #     "csv": AnalyzerExportRequest.FORMAT_CSV,
            #     "vcd": AnalyzerExportRequest.FORMAT_VCD,
            #     "native_saleae": AnalyzerExportRequest.FORMAT_NATIVE_SALEAE,
            #     "native_sigrok": AnalyzerExportRequest.FORMAT_NATIVE_SIGROK,
            # }.get(format.lower(), AnalyzerExportRequest.FORMAT_CSV)
            #
            # resp = self._call(
            #     "AnalyzerExport",
            #     AnalyzerExportRequest(
            #         capture_id=capture_id,
            #         format=format_enum,
            #         output_path=output_path,
            #     )
            # )
            #
            # if not resp.success:
            #     return resp.message, None
            # return None, resp.file_path

            return "AnalyzerExport not yet implemented in protocol", None

        except Exception as e:
            return f"analyzer_export error: {e}", None

    def analyzer_add_i2c_decoder(
        self,
        capture_id: str,
        sda_channel: int,
        scl_channel: int,
        decoder_name: str = "I2C",
    ) -> Tuple[Optional[str], Optional[str]]:
        """Add an I2C protocol decoder to a capture.

        Decodes I2C transactions from captured digital signals.

        Args:
            capture_id: Capture ID from analyzer_capture_start
            sda_channel: Channel number for SDA (data)
            scl_channel: Channel number for SCL (clock)
            decoder_name: Human-readable name for this decoder (default "I2C")

        Returns:
            (error, decoder_id) tuple. error is None on success.
            decoder_id is used to retrieve decoded data.

        Example:
            ```python
            err, dec_id = client.analyzer_add_i2c_decoder(
                cap_id, sda_channel=0, scl_channel=1
            )
            if not err:
                print(f"I2C decoder added: {dec_id}")
            ```
        """
        try:
            i2c_config = I2cDecoderConfig(
                sda_channel=sda_channel,
                scl_channel=scl_channel,
            )

            req = AddDecoderRequest(
                capture_id=capture_id,
                decoder_name=decoder_name,
                protocol=Protocol.PROTOCOL_I2C,
                i2c=i2c_config,
            )

            resp = self._call("AddDecoder", req)

            if not resp.success:
                return resp.message, None
            return None, resp.decoder_id

        except Exception as e:
            return f"analyzer_add_i2c_decoder error: {e}", None

    def analyzer_add_spi_decoder(
        self,
        capture_id: str,
        clk_channel: int,
        mosi_channel: int,
        miso_channel: int,
        cs_channel: int,
        cpol: bool = False,
        cpha: bool = False,
        bits_per_word: int = 8,
        msb_first: bool = True,
        decoder_name: str = "SPI",
    ) -> Tuple[Optional[str], Optional[str]]:
        """Add an SPI protocol decoder to a capture.

        Decodes SPI transactions from captured digital signals.

        Args:
            capture_id: Capture ID from analyzer_capture_start
            clk_channel: Channel number for CLK (clock)
            mosi_channel: Channel number for MOSI (master out, slave in)
            miso_channel: Channel number for MISO (master in, slave out)
            cs_channel: Channel number for CS (chip select)
            cpol: Clock polarity (default False)
            cpha: Clock phase (default False)
            bits_per_word: Bits per word (default 8)
            msb_first: MSB first (default True)
            decoder_name: Human-readable name for this decoder (default "SPI")

        Returns:
            (error, decoder_id) tuple. error is None on success.
            decoder_id is used to retrieve decoded data.

        Example:
            ```python
            err, dec_id = client.analyzer_add_spi_decoder(
                cap_id,
                clk_channel=0,
                mosi_channel=1,
                miso_channel=2,
                cs_channel=3,
            )
            if not err:
                print(f"SPI decoder added: {dec_id}")
            ```
        """
        try:
            spi_config = SpiDecoderConfig(
                clk_channel=clk_channel,
                mosi_channel=mosi_channel,
                miso_channel=miso_channel,
                cs_channel=cs_channel,
                cpol=cpol,
                cpha=cpha,
                bits_per_word=bits_per_word,
                msb_first=msb_first,
            )

            req = AddDecoderRequest(
                capture_id=capture_id,
                decoder_name=decoder_name,
                protocol=Protocol.PROTOCOL_SPI,
                spi=spi_config,
            )

            resp = self._call("AddDecoder", req)

            if not resp.success:
                return resp.message, None
            return None, resp.decoder_id

        except Exception as e:
            return f"analyzer_add_spi_decoder error: {e}", None

    def analyzer_get_decoded_data(
        self,
        capture_id: str,
        decoder_id: str = "",
    ) -> Tuple[Optional[str], list]:
        """Get decoded protocol data from a capture.

        Retrieves decoded protocol transactions (I2C, SPI, UART, etc.) from
        a completed capture.

        Args:
            capture_id: Capture ID from analyzer_capture_start
            decoder_id: Decoder ID (empty string returns data from all decoders)

        Returns:
            (error, decoded_data) tuple. error is None on success.
            decoded_data is a list of DecodedData protobuf messages.

        Example:
            ```python
            err, data = client.analyzer_get_decoded_data(cap_id, dec_id)
            if not err:
                for item in data:
                    if item.HasField("i2c"):
                        print(f"I2C: addr={item.i2c.address:02x}")
            ```
        """
        try:
            resp = self._call(
                "GetDecodedData",
                GetDecodedDataRequest(
                    capture_id=capture_id,
                    decoder_id=decoder_id,
                ),
            )

            if not resp.success:
                return resp.message, []
            return None, list(resp.data)

        except Exception as e:
            return f"analyzer_get_decoded_data error: {e}", []
