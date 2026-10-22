"""
While the MatrixOrbital library is MicroPython/CPython compatible,
this main script is intended to be used with MicroPython for launching
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

# Set GPIO pins.
tx_pin = 0
rx_pin = 1
button_pin = 2
dht_sensor_pin = 3
led_pin = 5

# Adjust the number of lines and columns that your display has.
lines = 4
cols = 20

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

# Weather and clock project that displays weather and time.
#weather_clock = WeatherClock(vfd, lines = lines, cols = cols, dht_pin = dht_sensor_pin, button_pin = button_pin)
weather_clock = WeatherClock(vfd, lines = lines, cols = cols, dht_pin = None, button_pin = None, led_pin = None)

# Start the main loop.
weather_clock.keepRunning()
