"""
Main script for driving the Noritake CU VFD using GPIO/parallel connection.

When using MicroPython, for example, on Raspberry Pi Pico,
this script will run automatically if you rename it to 'main.py'.
"""

from machine import Pin
import time

# Import Noritake Cu GPIO for interacting with Noritake VFD.
from noritake_cu_gpio import NoritakeCuGPIO

# Import Matrix Rain animation project.
# from projects.matrix_rain import MatrixRain
# Import Digital Clock project.
# from projects.clock import ClockTemp

# Allow time for the display to become ready for receiving commands.
time.sleep(1)

# Define the number of lines and columns in the display.
lines = 2
cols = 16

# Initialize Noritake VFD.
vfd = NoritakeCuGPIO(
    rs_pin = Pin(0),
    enable_pin = Pin(1),
    d4_pin = Pin(2),
    d5_pin = Pin(3),
    d6_pin = Pin(4),
    d7_pin = Pin(5),
    num_lines = lines,
    num_columns = cols
)

# Run Matrix Rain animation.
# rain = MatrixRain(vfd, lines, cols)
# rain.animate()

# Run Digital Clock.
# clock = ClockTemp(vfd, lines, cols)
# clock.keepRunning()
