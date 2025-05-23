# Standard library imports
from enum import Enum
from typing import Optional

# Third party imports
import gpiod
from gpiod.line import Value, Direction


class Pin(Enum):
    UNKNOWN = "UNKNOWN"  # Special case for invalid/unknown pins

    # ADC pins
    SODIMM_2 = "SODIMM_2"  # ADC_1, Analog Input 1
    SODIMM_4 = "SODIMM_4"  # ADC_2, Analog Input 2
    SODIMM_6 = "SODIMM_6"  # ADC_3, Analog Input 3
    SODIMM_8 = "SODIMM_8"  # ADC_4, Analog Input 4

    # I2C pins
    SODIMM_12 = "SODIMM_12"  # I2C1_SDA, Generic I2C Data
    SODIMM_14 = "SODIMM_14"  # I2C1_SCL, Generic I2C Clock
    SODIMM_55 = "SODIMM_55"  # I2C2_DSI_SDA, MIPI DSI I2C bus data
    SODIMM_53 = "SODIMM_53"  # I2C2_DSI_SCL, MIPI DSI I2C bus clock
    SODIMM_57 = "SODIMM_57"  # I2C3_HDMI_SDA, HDMI DDC I2C bus data
    SODIMM_59 = "SODIMM_59"  # I2C3_HDMI_SCL, HDMI DDC I2C bus clock
    SODIMM_95 = "SODIMM_95"  # I2C4_CSI_SDA, MIPI CSI camera control I2C bus data
    SODIMM_93 = "SODIMM_93"  # I2C4_CSI_SCL, MIPI CSI camera control I2C bus clock

    # PWM pins
    SODIMM_15 = "SODIMM_15"  # PWM_1, General-purpose PWM 1
    SODIMM_16 = "SODIMM_16"  # PWM_2, General-purpose PWM 2 (LVDS backlight)

    # GPIO pins
    SODIMM_206 = "SODIMM_206"  # GPIO_1, General-purpose I/O
    SODIMM_208 = "SODIMM_208"  # GPIO_2, General-purpose I/O
    SODIMM_210 = "SODIMM_210"  # GPIO_3, General-purpose I/O
    SODIMM_212 = "SODIMM_212"  # GPIO_4, General-purpose I/O

    # SPI pins
    SODIMM_196 = "SODIMM_196"  # SPI_1_CLK, Serial Clock
    SODIMM_198 = "SODIMM_198"  # SPI_1_MISO, Master Input Slave Output
    SODIMM_200 = "SODIMM_200"  # SPI_1_MOSI, Master Output Slave Input
    SODIMM_202 = "SODIMM_202"  # SPI_1_CS, Chip Select

    # CAN pins
    SODIMM_20 = "SODIMM_20"  # CAN_1_TX, CAN port 1 transmit
    SODIMM_22 = "SODIMM_22"  # CAN_1_RX, CAN port 1 receive
    SODIMM_24 = "SODIMM_24"  # CAN_2_TX, CAN port 2 transmit
    SODIMM_26 = "SODIMM_26"  # CAN_2_RX, CAN port 2 receive

    # I2S pins
    SODIMM_30 = "SODIMM_30"  # I2S_1_BCLK, Serial audio bit clock
    SODIMM_32 = "SODIMM_32"  # I2S_1_SYNC, Left-right channel select
    SODIMM_34 = "SODIMM_34"  # I2S_1_D_OUT, Serial audio output
    SODIMM_36 = "SODIMM_36"  # I2S_1_D_IN, Serial audio input
    SODIMM_38 = "SODIMM_38"  # I2S_1_MCLK, Serial audio master clock

    # UART pins
    SODIMM_129 = "SODIMM_129"  # UART_1_RXD, UART1 Receive Data
    SODIMM_131 = "SODIMM_131"  # UART_1_TXD, UART1 Transmit Data
    SODIMM_133 = "SODIMM_133"  # UART_1_RTS, UART1 Request to Send
    SODIMM_135 = "SODIMM_135"  # UART_1_CTS, UART1 Clear to Send
    SODIMM_137 = "SODIMM_137"  # UART_2_RXD, UART2 Receive Data
    SODIMM_139 = "SODIMM_139"  # UART_2_TXD, UART2 Transmit Data
    SODIMM_141 = "SODIMM_141"  # UART_2_RTS, UART2 Request to Send
    SODIMM_143 = "SODIMM_143"  # UART_2_CTS, UART2 Clear to Send

    @classmethod
    def from_str(cls, pin_str: str) -> "Pin":
        """Convert string to Pin enum value.

        Args:
            pin_str: String representation of pin (e.g., "SODIMM_22")

        Returns:
            Pin enum value (UNKNOWN if not found)
        """
        try:
            return cls(pin_str.upper())
        except ValueError:
            return cls.UNKNOWN

    def is_valid(self) -> bool:
        """Check if this is a valid GPIO pin."""
        return self != Pin.UNKNOWN

    def __str__(self) -> str:
        """Return string representation of pin."""
        return self.value


class Gpio:
    def __init__(self, consumer: str, pin: Pin, direction: Direction):
        self.consumer = consumer
        self.pin = pin
        self.direction = direction
        self.request: Optional[gpiod.LineRequest] = None

    def init(self) -> Optional[str]:
        """Initialize the GPIO line."""
        if not self.pin.is_valid():
            return "Invalid GPIO pin"

        try:
            # Find the line by name across all chips
            for chip_num in range(5):  # we typically have gpiochip0 through gpiochip4
                try:
                    with gpiod.Chip(f"/dev/gpiochip{chip_num}") as gpio_chip:
                        config = {
                            self.pin.value: gpiod.LineSettings(direction=self.direction, output_value=Value.INACTIVE)
                        }
                        self.request = gpio_chip.request_lines(config=config, consumer=self.consumer)
                        return None
                except PermissionError:
                    return f"Permission denied: cannot access GPIO. Try running with sudo or check udev rules"
                except Exception:
                    continue
            return f"GPIO pin {self.pin.value} not found"
        except Exception as e:
            return f"Failed to initialize GPIO: {str(e)}"

    def write(self, value: int) -> Optional[str]:
        """Write a value to the GPIO line."""
        if not self.request:
            return "GPIO not initialized"
        try:
            self.request.set_value(self.pin.value, Value.ACTIVE if value else Value.INACTIVE)
            return None
        except PermissionError:
            return "Permission denied: cannot write to GPIO. Try running with sudo or check udev rules"
        except Exception as e:
            return f"Failed to write to GPIO: {str(e)}"

    def read(self) -> tuple[Optional[str], int]:
        """Read the current value of the GPIO line."""
        if not self.request:
            return "GPIO not initialized", 0
        try:
            value = self.request.get_value(self.pin.value)
            return None, 1 if value == Value.ACTIVE else 0
        except PermissionError:
            return "Permission denied: cannot read from GPIO. Try running with sudo or check udev rules", 0
        except Exception as e:
            return f"Failed to read GPIO: {str(e)}", 0

    def deinit(self) -> Optional[str]:
        """Release the GPIO line."""
        if self.request:
            try:
                self.request.release()
                self.request = None
                return None
            except PermissionError:
                return "Permission denied: cannot release GPIO. Try running with sudo or check udev rules"
            except Exception as e:
                return f"Failed to release GPIO: {str(e)}"
        return None

    def __enter__(self):
        err = self.init()
        if err:
            raise RuntimeError(err)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.deinit()
