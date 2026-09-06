"""
A library for interacting with Noritake Itron CU Series VFD'
over an I2C connection.

Use HD44780 compatible I2C display controller to communicate with the VFD.

Requires https://github.com/dhylands/python_lcd files (included in the lib folder):
- lcd_api.py
- machine_i2c.py

Example usage:

i2c = I2C(0, scl = Pin(1), sda = Pin(0))
vfd = NoritakeCuI2C(
    i2c = i2c,
    i2c_addr = 0x27,
    num_lines = 2,
    num_columns = 16,
)
vfd.write('Hello')

See the below functions and NoritakeCuFunctions() functions
to review what commands are available.
"""

# Include 'lib.' for IDE to see the file.
from lib.machine_i2c_lcd import I2cLcd

from noritake_cu_functions import NoritakeCuFunctions

class NoritakeCuI2C(I2cLcd, NoritakeCuFunctions):
    """Implements a Noritake Itron VFD connected via I2C."""

    def __init__(self, i2c, i2c_addr, num_lines = 2, num_columns = 16):
        super().__init__(i2c, i2c_addr, num_lines, num_columns)

    # .-----------------------------------------------------.
    # |                  GENERAL COMMANDS                   |
    # '-----------------------------------------------------'

    def setBrightness(self, brightness):
        """
        Sets brightness level (1-4).

        Noritake command: 7.7.2 - Brightness control

        :param brightness: 0 for 100%, 1 for 75%, 2 for 50%, and 3 for 25%.
        """
        # It's not possible to set VFD brightness using I2C.
        pass
