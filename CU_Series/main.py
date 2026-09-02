"""
Main script for starting the Noritake CU VFD.

If you are using MicroPython, for example, on Raspberry Pi Pico,
this script will run automatically.

When using regular Raspberry Pi, you need to manually run this script
and instead of importing micropython 'machine' use 'gpiozero' or 'RPi.GPIO'.
"""

from machine import Pin, I2C
import time

# Import either Noritake GPIO or Noritake I2C.
from noritake_cu_gpio import NoritakeGPIO
from noritake_cu_i2c import NoritakeI2C

# Import Matrix Rain animation demo.
from demo.matrix_rain import MatrixRain
# Import digital clock demo.
from demo.clock import ClockTemp

# Allow time for the display to become ready for receiving commands.
time.sleep(1)

# Define the number of lines and columns in the display.
lines = 2
cols = 16

# VFD over GPIO.
# Requires 'from noritake_gpio import Noritake'.

# Initialize Noritake VFD.
vfd = NoritakeGPIO(
    rs_pin = Pin(0),
    enable_pin = Pin(1),
    d4_pin = Pin(2),
    d5_pin = Pin(3),
    d6_pin = Pin(4),
    d7_pin = Pin(5),
    num_lines = lines,
    num_columns = cols
)

# VFD over I2C.
# Requires 'from noritake_gpio import Noritake'.

# Initialize Noritake VFD.
# i2c = I2C(0, scl = Pin(1), sda = Pin(0))
#
# vfd = NoritakeI2C(
#     i2c = i2c,
#     i2c_addr = 0x27,
#     num_lines = lines,
#     num_columns = cols
# )

# Demo: Matrix Rain animation.
#rain = MatrixRain(vfd, lines, cols)
#rain.animate()

# Demo: Digital clock.
clock = ClockTemp(vfd, lines, cols)
clock.keepRunning()
