"""
A Noritake GU series VFD parallel connection class.

Platform: CPython on Raspberry Pi with RPi.GPIO.

This class allows communicating with the Noritake GU series VFDs over
a parallel bus.
"""

import time
import RPi.GPIO as GPIO

class NoritakeGuParallel:

    def __init__(self, data_pins, wr_pin, rdy_pin, pin_mode = GPIO.BCM):
        """
        Initialize the Noritake VFD Parallel interface.

        :param data_pins: List of 8 GPIO numbers for D0-D7.
        :param wr_pin: GPIO number for the WR (Write) signal.
        :param rdy_pin: GPIO number for the RDY/BUSY signal.
        :param pin_mode: RPi.GPIO pin numbering mode.
        """
        GPIO.setmode(pin_mode)

        # Initialize 8-bit data bus (D0 to D7).
        self.data_pins = data_pins
        for p in self.data_pins:
            GPIO.setup(p, GPIO.OUT)

        # Initialize control pins.
        # Active Low.
        self.wr_pin = wr_pin
        GPIO.setup(self.wr_pin, GPIO.OUT, initial = GPIO.HIGH)
        # 1 = Ready.
        self.rdy_pin = rdy_pin
        GPIO.setup(self.rdy_pin, GPIO.IN)

    def sendByte(self, byte: int):
        """
        Sends a single byte over the parallel bus.

        :param byte: The byte to send.
        """
        # Wait until the display is ready (RDY = 1)
        while not GPIO.input(self.rdy_pin):
            time.sleep(0.001)

        # Apply byte to data pins.
        for bit in range(8):
            GPIO.output(self.data_pins[bit], GPIO.HIGH if (byte >> bit) & 0x01 else GPIO.LOW)

        # Pulse the writing signal.
        GPIO.output(self.wr_pin, GPIO.LOW)
        # Pulse duration is naturally handled by python's overhead.
        GPIO.output(self.wr_pin, GPIO.HIGH)

    def write(self, data):
        """
        Universal write method for commands, strings, byte arrays, etc.

        :param data: The data to write.
        """
        if isinstance(data, str):
            for char in data:
                self.sendByte(ord(char))

        elif isinstance(data, (list, tuple, bytes, bytearray)):
            for byte in data:
                self.sendByte(byte)

        elif isinstance(data, int):
            self.sendByte(data & 0xFF)

        else:
            raise TypeError('Unsupported data type for write().')
