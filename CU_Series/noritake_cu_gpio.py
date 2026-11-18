"""
A Library for interacting with Noritake Itron CU Series VFD's
over a parallel/GPIO connection.

Use 4 or 8 data wires and 'rw' + 'enable' wires to communicate with the VFD.

Requires https://github.com/dhylands/python_lcd files (included in the lib folder):
- lcd_api.py
- esp32_gpio_lcd.py

Example usage:

vfd = NoritakeCuGPIO(
    rs_pin = Pin(0),
    enable_pin = Pin(1),
    d4_pin = Pin(2),
    d5_pin = Pin(3),
    d6_pin = Pin(4),
    d7_pin = Pin(5),
    num_lines = 2,
    num_columns = 16,
)
vfd.write('Hello')

See the below functions and NoritakeCuFunctions() functions
to review what commands are available.
"""

# Include 'lib.' for IDE to see the file.
from lib.esp32_gpio_lcd import GpioLcd

from noritake_cu_functions import NoritakeCuFunctions

class NoritakeCuGPIO(GpioLcd, NoritakeCuFunctions):
    """
    Implements a Noritake Itron VFD connected via GPIO pins.

    Pin arguments must be machine.Pin objects, or None for unused pins.
    For 4-bit mode, provide d4_pin through d7_pin and leave d0_pin through
    d3_pin as None. For 8-bit mode, provide all eight data pins.

    :param rs_pin: Register select pin (RS).
    :param enable_pin: Enable pin (E).
    :param d0_pin: Data pin D0; unused in 4-bit mode. Default is None.
    :param d1_pin: Data pin D1; unused in 4-bit mode. Default is None.
    :param d2_pin: Data pin D2; unused in 4-bit mode. Default is None.
    :param d3_pin: Data pin D3; unused in 4-bit mode. Default is None.
    :param d4_pin: Data pin D4; required in both 4-bit and 8-bit modes.
    :param d5_pin: Data pin D5; required in both 4-bit and 8-bit modes.
    :param d6_pin: Data pin D6; required in both 4-bit and 8-bit modes.
    :param d7_pin: Data pin D7; required in both 4-bit and 8-bit modes.
    :param rw_pin: Optional read/write pin, held low for write-only operation.
      The default is None; connect the display's R/W line to ground if omitted.
    :param backlight_pin: Optional backlight control pin supported by the base
      LCD driver. Usually unused for a VFD. Default is None.
    :param num_lines: The number of display lines. Default is 2.
    :param num_columns: The number of display columns. Default is 16.
    """

    def __init__(self, rs_pin, enable_pin, d0_pin=None, d1_pin=None,
             d2_pin=None, d3_pin=None, d4_pin=None, d5_pin=None,
             d6_pin=None, d7_pin=None, rw_pin=None, backlight_pin=None,
             num_lines=2, num_columns=16):
        super().__init__(rs_pin, enable_pin, d0_pin, d1_pin,
             d2_pin, d3_pin, d4_pin, d5_pin,
             d6_pin, d7_pin, rw_pin, backlight_pin,
             num_lines, num_columns)

    # .-----------------------------------------------------.
    # |                  GENERAL COMMANDS                   |
    # '-----------------------------------------------------'

    def setBrightness(self, brightness):
        """
        Sets brightness level (1-4).

        Noritake command: 7.7.2 - Brightness control

        :param brightness: 4 for 100%, 3 for 75%, 2 for 50%, and 1 for 25%.
        """
        levels = {
            1: 0x03,
            2: 0x02,
            3: 0x01,
            4: 0x00
        }

        # Validate the brightness before sending commands to the display.
        if brightness not in levels:
            raise ValueError('Brightness must be between 1 and 4.')

        self.rs_pin.value(0)
        self.hal_write_8bits(
            self.LCD_FUNCTION
            | (0 if self._4bit else self.LCD_FUNCTION_8BIT)
        )

        self.rs_pin.value(1)
        self.hal_write_8bits(levels[brightness])
