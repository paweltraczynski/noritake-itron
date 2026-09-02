"""
Main script for driving the Noritake CU VFD using I2C connection.

If you are using MicroPython, for example, on Raspberry Pi Pico,
this script will run automatically if you rename it to 'main.py'.

When using regular Raspberry Pi, you need to manually run this script
and instead of importing MicroPython 'machine' use 'gpiozero' or 'RPi.GPIO'
and import Pin from it.
"""

from machine import Pin, I2C
import time

# Import Noritake I2C for interacting with Noritake VFD.
from noritake_cu_i2c import NoritakeI2C
# Import Matrix Rain animation demo.
from demo.matrix_rain import MatrixRain

# Allow time for the display to become ready for receiving commands.
time.sleep(1)

# Define the number of lines and columns in the display.
lines = 2
cols = 16

# Initialize Noritake VFD.
i2c = I2C(0, scl = Pin(1), sda = Pin(0))

vfd = NoritakeI2C(
    i2c = i2c,
    i2c_addr = 0x27,
    num_lines = lines,
    num_columns = cols
)

# Run Matrix Rain animation.
# rain = MatrixRain(vfd = vfd, lines = lines, cols = cols)
# rain.animate()
