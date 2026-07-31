"""
Custom library for interacting with Noritake Itron CU Series VFD's.

Use HD44780 compatible i2c display controller to communicate with the VFD.

Requires https://github.com/dhylands/python_lcd files:
- lcd_api.py
- machine_i2c.py

Example usage:

i2c = I2C(0, scl = Pin(1), sda = Pin(0))

vfd = NoritakeI2C(
    i2c = i2c,
    i2c_addr = 0x27,
    num_lines = 2,
    num_columns = 16
)

vfd.write('Hello')

See the below functions and lcd_api.py functions.
"""

from noritake_cu_functions import NoritakeFunctions
from machine_i2c_lcd import I2cLcd

class NoritakeI2C(NoritakeFunctions, I2cLcd):
    """Implements a Noritake Itron VFD connected via I2C."""

    def __init__(self, i2c, i2c_addr, num_lines = 2, num_columns = 16):
        super().__init__(i2c, i2c_addr, num_lines, num_columns)

    # .-----------------------------------------------------.
    # |                  GENERAL COMMANDS                   |
    # '-----------------------------------------------------'

    def setBrightness(self):
        """
        Sets brightness level (1-4).

        Noritake command: 7.7.2 - Brightness control
        """
        # It's not possible to set VFD brightness using I2C.
        pass
