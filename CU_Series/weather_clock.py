"""
This main script is intended to be used with MicroPython for launching
the weather display project, which was written for MicroPython.
"""
import time
from machine import UART, Pin

# Import Noritake Cu GPIO for interacting with Noritake VFD.
from noritake_cu_gpio import NoritakeCuGPIO

# Import weather clock.
from demo.weather_clock import WeatherClock

# Allow time for the display to become ready for receiving commands.
time.sleep(1)

# Set GPIO pins, e.g., 3, 2, 5.
dht_pin = 10
button_pin = 12
led_pin = 11

# Adjust the number of lines and columns that your display has.
lines = 4
cols = 20

# Initialize Noritake VFD.
vfd = NoritakeCuGPIO(
    rs_pin = Pin(0),
    enable_pin = Pin(1),
    d4_pin = Pin(6),
    d5_pin = Pin(7),
    d6_pin = Pin(8),
    d7_pin = Pin(9),
    num_lines = lines,
    num_columns = cols
)

# Weather and clock project that displays weather and time.
weather_clock = WeatherClock(
    vfd = vfd,
    lines = lines,
    cols = cols,
    dht_pin = dht_pin,
    button_pin = button_pin,
    led_pin = led_pin
)

# Start the main loop.
weather_clock.keepRunning()
