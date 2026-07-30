"""
Custom library for interacting with Noritake Itron CU Series VFD's.

Use 4 or 8 data wires and 'rw' + 'enable' wires to communicate with the VFD.

Requires https://github.com/dhylands/python_lcd files:
- lcd_api.py
- esp32_gpio_lcd.py

Example usage:

vfd = Noritake(
    rs_pin = Pin(0),
    enable_pin = Pin(1),
    d4_pin = Pin(2),
    d5_pin = Pin(3),
    d6_pin = Pin(4),
    d7_pin = Pin(5),
    num_lines = 2,
    num_columns = 16
)

vfd.write('Hello')

See the below functions and lcd_api.py functions.
"""

from esp32_gpio_lcd import GpioLcd

class NoritakeGPIO(GpioLcd):
    """Implements a Noritake Itron VFD connected via GPIO pins."""

    def __init__(self, rs_pin, enable_pin, d0_pin=None, d1_pin=None,
             d2_pin=None, d3_pin=None, d4_pin=None, d5_pin=None,
             d6_pin=None, d7_pin=None, rw_pin=None, backlight_pin=None,
             num_lines=2, num_columns=16):
        super().__init__(rs_pin, enable_pin, d0_pin, d1_pin,
             d2_pin, d3_pin, d4_pin, d5_pin,
             d6_pin, d7_pin, rw_pin, backlight_pin,
             num_lines, num_columns)

        self.cursor_x = 0
        self.cursor_y = 0

    # .-----------------------------------------------------.
    # |                  WRITING COMMANDS                   |
    # '-----------------------------------------------------'

    def write(self, data):
        """
        Universal write method for commands, strings, or byte arrays.

        :param data: The data to write - can be text or command bytes.
        """
        if isinstance(data, str):
            self.writeText(data)

        elif isinstance(data, (list, tuple, bytes, bytearray)):
            for byte in data:
                self.writeCommand(byte)

        elif isinstance(data, int):
            self.writeCommand(data & 0xFF)

        else:
            raise TypeError('Unsupported data type for write().')

    def writeCommand(self, data):
        """
        Writes a command to the display.

        :param data: The command to write.
        """
        self.hal_write_command(data)

    def writeText(self , data):
        """
        Writes text on the display at the cursor position.

        :param data: The text string to write of the display.
        """
        self.putstr(data)

    def writeDataByte(self, data):
        """
        Writes data to the display.

        :param data: The data to write.
        """
        self.hal_write_data(data)

    def writeCustomChar(self, location, charmap):
        """
        "Write a custom character to one of the 8 CGRAM locations.

        :param location: The location to write the character to (0-7)
        :param charmap: The character map to write to the location.
        """
        self.custom_char(location, charmap)

    # .-----------------------------------------------------.
    # |                 NAVIGATION COMMANDS                 |
    # '-----------------------------------------------------'

    def setCursor(self, column, row):
        """
        Puts the cursor at the specified column and row.

        Noritake command: 7.9 - Set DD RAM address.

        :param column: The column to move the cursor to.
        :param row: The row to move the cursor to.

        """
        self.move_to(column, row)

    def cursorLeft(self, amount = 1):
        """
        Moves the cursor left by the specified number of characters.

        Noritake command: 7.6 - Cursor/display shift: cursor left.

        :param amount: By how many characters to move the cursor left.
        """
        for _ in range(amount):
            if self.cursor_x > 0:
                self.writeCommand(self.LCD_MOVE)
                self.cursor_x -= 1

    def cursorRight(self, amount = 1):
        """
        Moves the cursor right by the specified number of characters.

        Noritake command: 7.6 - Cursor/display shift: cursor right.

        :param amount: By how many characters to move the cursor right.
        """
        for _ in range(amount):
            if self.cursor_x < self.num_columns:
                self.writeCommand(self.LCD_MOVE | self.LCD_MOVE_RIGHT)
                self.cursor_x += 1

    def cursorUp(self, amount):
        """
        Moves the cursor up by the specified number of lines.

        :param amount: By how many lines to move the cursor up.
        """
        y = self.cursor_y - amount

        if y < 0:
            y = 0

        self.setCursor(self.cursor_x, y)

    def cursorDown(self, amount = 1):
        """
        Moves the cursor down by the specified number of lines.

        :param amount: By how many lines to move the cursor down.
        """
        lines = self.num_lines
        y = self.cursor_y + amount

        if y > lines - 1:
            y = lines - 1

        self.setCursor(self.cursor_x, y)

    def cursorHome(self):
        """
        Moves the cursor to the home position.

        Noritake command: 7.3 - Cursor home.
        """
        self.writeCmmand(self.LCD_HOME)
        self.cursor_x = 0
        self.cursor_y = 0

    def cursorReturn(self):
        """
        Moves the cursor to the start of the current line.
        """
        self.setCursor(0, self.cursor_y)

    # .-----------------------------------------------------.
    # |                  CLEARING  COMMANDS                 |
    # '-----------------------------------------------------'

    def clearDisplay(self):
        """
        Clears the display and moves the cursor to the home position.

        Noritake command: 7.2 - Display clear.
        """
        self.clear()

    def clearLine(self):
        """
        Clears the current line and moves the cursor to the line start.

        Puts cursor at the start of the line, then fills the line
        with spaces, then moves cursor to start.
        """
        self.setCursor(0, self.cursor_y)
        self.writeText(' ' * self.num_columns)
        self.setCursor(0, self.cursor_y)

    def clearLineRight(self):
        """
        Clear the current line from the cursor position to the end of the line.

        Writes spaces to the end of the line,
        then moves the cursor back to where it was.
        """
        x = self.cursor_x
        self.writeText(' ' * (self.num_columns - self.cursor_x))
        self.setCursor(x, self.cursor_y)

    # .-----------------------------------------------------.
    # |                  GENERAL COMMANDS                   |
    # '-----------------------------------------------------'

    def setBrightness(self, value):
        """
        Sets brightness level (1-4).

        Noritake command: 7.7.2 - Brightness control
        """
        levels = {
            1: 0x00,
            2: 0x01,
            3: 0x02,
            4: 0x03
        }

        self.rs_pin.value(0)
        self.hal_write_8bits(self.LCD_FUNCTION)

        self.rs_pin.value(1)
        self.hal_write_8bits(levels[value])

    def underlineCursor(self, enable):
        """
        Enables or disables the underline cursor.

        Noritake command: 7.5 - Display on/off: underline cursor.

        :param enable: True to enable the underline cursor, False to disable it.
        """
        if enable:
            self.show_cursor()
        else:
            self.hide_cursor()

    def blockCursor(self, enable):
        """
        Enables or disables the blinking block cursor.

        Noritake command: 7.5 - Display on/off: block cursor.

        :param enable: True to enable the blinking block cursor, False to disable it.
        """
        if enable:
            self.blink_cursor_on()
        else:
            self.blink_cursor_off()

    # .-----------------------------------------------------.
    # |               DISPLAY ACTION COMMANDS               |
    # '-----------------------------------------------------'

    def displayOnOff(self, on_off):
        """
        Turns the display on or off.

        Noritake command: 7.5 - Display on/off: display.

        :param on_off: True to turn the display on, False to turn it off.
        """
        if on_off:
            self.display_on()
        else:
            self.display_off()

    # .-----------------------------------------------------.
    # |                DISPLAY MOVE COMMANDS                |
    # '-----------------------------------------------------'

    def entryModeSet(self, direction, shift):
        """
        Sets the address counter direction and specifies display shift.

        Address counter direction:
        Selects the way in which the contents of the address counter
        are modified after every access to DD RAM or CG RAM.

        Noritake command: 7.4 - Entry mode set.

        :param direction: The address counter direction (increment/decrement).
        :param shift: Cursor/display shift (cursor/display).
        """
        if direction == 'increment':
            if shift == 'cursor':
                self.writeCommand(self.LCD_ENTRY_MODE | self.LCD_ENTRY_INC)
            else:
                self.writeCommand(self.LCD_ENTRY_MODE | self.LCD_ENTRY_INC | self.LCD_ENTRY_SHIFT)
        else:
            if shift == 'cursor':
                self.writeCommand(self.LCD_ENTRY_MODE)
            else:
                self.writeCommand(self.LCD_ENTRY_MODE | self.LCD_ENTRY_SHIFT)

    def displayLeft(self, amount = 1):
        """
        Shifts the entire display to the left.

        Noritake command: 7.6 - Cursor/display shift: display left.

        :param amount: By how many characters to move the display left.
        """
        for _ in range(amount):
            self.writeCommand(self.LCD_MOVE | self.LCD_MOVE_DISP)

    def displayRight(self, amount = 1):
        """
        Shifts the entire display to the right.

        Noritake command: 7.6 - Cursor/display shift: display right.

        :param amount: By how many characters to move the display right.
        """
        for _ in range(amount):
            self.writeCommand(self.LCD_MOVE | self.LCD_MOVE_DISP | self.LCD_MOVE_RIGHT)
