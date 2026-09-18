"""
A Noritake GU series VFD parallel connection class.

Platform: MicroPython with machine.Pin.

This class allows communicating with the Noritake GU series VFDs over
a parallel bus.
"""

import time
from machine import Pin

class NoritakeGuParallel:

    def __init__(self, data_pins, wr_pin, rdy_pin):
        """
        Initialize the Noritake VFD Parallel interface.

        :param data_pins: List of 8 GPIO numbers for D0-D7.
        :param wr_pin: GPIO number for the WR (Write) signal.
        :param rdy_pin: GPIO number for the RDY/BUSY signal.
        """
        # Initialize 8-bit data bus (D0 to D7).
        self.data_pins = [Pin(p, Pin.OUT) for p in data_pins]

        # Initialize control pins.
        # Active Low.
        self.wr_pin = Pin(wr_pin, Pin.OUT, value = 1)
        # 1 = Ready.
        self.rdy_pin = Pin(rdy_pin, Pin.IN)

    def sendByte(self, byte):
        """
        Sends a single byte over the parallel bus.

        :param byte: The byte to send.
        """
        # Wait until the display is ready (RDY = 1)
        while not self.rdy_pin.value():
            time.sleep(0.001)

        # Apply byte to data pins.
        for bit in range(8):
            self.data_pins[bit].value((byte >> bit) & 0x01)

        # Pulse the writing signal.
        self.wr_pin.value(0)
        # Pulse duration is naturally handled by python's overhead.
        self.wr_pin.value(1)

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
