"""
Custom library for interacting with Noritake Itron CU Series VFD's.

Use 4 or 8 data wires and 'rw' + 'enable' wires to communicate with the VFD.

Requires https://github.com/dhylands/python_lcd files:
- lcd_api.py
- esp32_gpio_lcd.py

Example usage:

vfd = Noritake(
    rs_pin = Pin(0),
    enable_pin = Pin(1),
    d4_pin = Pin(2),
    d5_pin = Pin(3),
    d6_pin = Pin(4),
    d7_pin = Pin(5),
    num_lines = 2,
    num_columns = 16
)

vfd.write('Hello')

See the below functions and lcd_api.py functions.
"""

from noritake_cu_functions import NoritakeFunctions
from esp32_gpio_lcd import GpioLcd

class NoritakeGPIO(NoritakeFunctions, GpioLcd):
    """Implements a Noritake Itron VFD connected via GPIO pins."""

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

        :param brightness: 0 for 100%, 1 for 75%, 2 for 50% and 3 for 25%.
        """
        levels = {
            1: 0x00,
            2: 0x01,
            3: 0x02,
            4: 0x03
        }

        self.rs_pin.value(0)
        self.hal_write_8bits(self.LCD_FUNCTION)

        self.rs_pin.value(1)
        self.hal_write_8bits(levels[brightness])
