"""
A demo for printing Matrix Rain animation on Noritake CU VFD's.

Usage:

from machine import Pin
import time
from noritake_gpio import Noritake
from matrix_rain import MatrixRain

# Allow time for the display to become ready for receiving commands.
time.sleep(1)

# Define the number of lines and columns in the display:
lines = 2
cols = 24

# Initialize Noritake VFD:
vfd = Noritake(
    rs_pin = Pin(0),
    enable_pin = Pin(1),
    d4_pin = Pin(2),
    d5_pin = Pin(3),
    d6_pin = Pin(4),
    d7_pin = Pin(5),
    num_lines = lines,
    num_columns = cols)

rain = MatrixRain(vfd, lines, cols)
rain.animate()
"""

import time
import random

class MatrixRain:
    """
    Displays a Matrix Rain animation.
    """

    def __init__(self, vfd, lines, cols):
        self.vfd = vfd
        self.lines = lines
        self.cols = cols

        # Configuration.
        self.chars_block_min = 6
        self.chars_block_max = 14
        self.spaces_block_min = 2
        self.spaces_block_max = 4
        self.animation_interval = 0.15

        # Prepare initial matrix chars dictionary.
        self.chars = {}
        # And ended chars that just left the screen.
        self.end_chars = {}
        # Keep track of how many spaces or chars were recently printed.
        self.space_count = {}
        self.char_count = {}

        # Build the initial matrix chars dictionary.
        for line_key in range(lines):
            self.chars[line_key] = {}
            self.end_chars[line_key] = 0
            self. space_count[line_key] = 0
            self.char_count[line_key] = 0
            for col_key in range(cols):
                self.chars[line_key][col_key] = self.get_space()

    def get_space(self):
        """
        Function for getting a space character.

        :return hex: A space character encoded as a hex value.
        """
        return 0x00 | 0x20

    def get_char(self):
        """
        Function for getting a matrix symbol character.

        :return hex: A matrix symbol character encoded as a hex value.
        """
        # We are using two columns of 16 symbols each.
        # Most of them are Japanese characters in the
        # character set of the Noritake CU.
        matrix_chars_hex1 = [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f]
        matrix_chars_hex2 = [0xb0, 0xc0, 0xd0]

        # We randomly select indexes instead of using random.choice().
        idx1 = random.randint(0, len(matrix_chars_hex1) - 1)
        idx2 = random.randint(0, len(matrix_chars_hex2) - 1)

        # noinspection PyTypeChecker, PyNoneFunctionAssignment, PyUnresolvedReferences
        return matrix_chars_hex1[idx1] | matrix_chars_hex2[idx2]

    def print_matrix_chars(self):
        """
        Prints all current matrix chars to the display.
        """
        for line in range(self.lines):
            for col in range(self.cols):
                self.vfd.setCursor(col, line)
                self.vfd.writeData(self.chars[line][col])

    def move_matrix_chars(self):
        """
        Moves matrix chars in the self.chars by one column while shuffling new incoming chars.
        """
        new_chars = {}

        for line in range(self.lines):
            new_chars[line] = {}

            for col in range(self.cols):
                # First col: draw a new char and count chars/spaces.
                if col == 0:
                    # Printing block of chars, min 6, max 14.
                    if self.char_count[line] != 0 and self.char_count[line] <= random.randint(self.chars_block_min, self.chars_block_max):
                        new_chars[line][col] = self.get_char()
                        self.char_count[line] += 1

                    # Printing block of spaces, min 2, max 6.
                    elif self.space_count[line] != 0 and self.space_count[line] <= random.randint(self.spaces_block_min, self.spaces_block_max):
                        new_chars[line][col] = self.get_space()
                        self.space_count[line] += 1

                    # After block of chars put first space.
                    elif self.char_count[line] != 0 and self.space_count[line] == 0:
                        new_chars[line][col] = self.get_space()
                        self.space_count[line] += 1
                        self.char_count[line] = 0

                    # After block of spaces put first char.
                    elif self.space_count[line] != 0 and self.char_count[line] == 0:
                        new_chars[line][col] = self.get_char()
                        self.char_count[line] += 1
                        self.space_count[line] = 0

                    # When the script starts, randomize what's first.
                    else:
                        if random.randint(0, 1) == 0:
                            new_chars[line][col] = self.get_char()
                            self.char_count[line] += 1
                            self.space_count[line] = 0
                        else:
                            new_chars[line][col] = self.get_space()
                            self.space_count[line] += 1
                            self.char_count[line] = 0

                # Remaining cols: shift chars, get new char if after space.
                else:
                    prev_col = col - 1
                    next_col = col + 1

                    # Get prev char (from next col).
                    if next_col == self.cols:
                        prev_char = self.end_chars[line]
                    else:
                        prev_char = self.chars[line][col]

                    # Char after space should always change.
                    if prev_char == self.get_space() and self.chars[line][prev_col] != self.get_space():
                        new_chars[line][col] = self.get_char()
                    else:
                        new_chars[line][col] = self.chars[line][prev_col]

            # Save character that just left the screen.
            self.end_chars[line] = self.chars[line][self.cols - 1]

        self.chars = new_chars

    def animate(self, timeout = None):
        """
        Starts the Matrix Rain animation.

        :param timeout: The time in seconds after which the function will exit. If None, the animation will run forever.
        """
        self.vfd.clearDisplay()
        self.print_matrix_chars()

        start_time = time.ticks_ms()

        while True:
            # Exit after the timeout.
            if timeout and time.ticks_diff(time.ticks_ms(), start_time) >= (timeout * 1000):
                break

            self.move_matrix_chars()
            self.print_matrix_chars()
            time.sleep(self.animation_interval)
