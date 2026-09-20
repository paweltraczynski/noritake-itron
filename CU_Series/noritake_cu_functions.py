"""
Noritake Itron CU Series VFD's - API functions.
"""

from lib.lcd_api import LcdApi

class NoritakeCuFunctions(LcdApi):
    """
    Noritake CU functions for the CU Series displays.
    """

    # .-----------------------------------------------------.
    # |                  WRITING COMMANDS                   |
    # '-----------------------------------------------------'

    def write(self, data):
        """
        Universal write method for text strings and commands.

        :param data: The data to write - can be text or command bytes.
        """
        if isinstance(data, str):
            self.writeText(data)

        elif isinstance(data, (list, tuple, bytes, bytearray)):
            for byte in data:
                self.writeCommand(byte)

        elif isinstance(data, int):
            self.writeCommand(data)

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

    def writeData(self, data):
        """
        Writes data to the display.

        :param data: The data to write.
        """
        if isinstance(data, (list, tuple, bytes, bytearray)):
            for byte in data:
                self.hal_write_data(byte)
        else:
            self.hal_write_data(data)

    def writeCustomChar(self, location, charmap):
        """
        "Writes a custom character to one of the 8 CGRAM locations.

        :param location: The location to write the character to (0-7)
        :param charmap: The character map to write to the location.
        """
        self.custom_char(location, charmap)

    def writeNamedChar(self, name):
        """
        Writes a named character on the display at the cursor position.

        This allows writing special characters that can be used as
        built-in icons (e.g. arrows, circles, etc.)

        :param name: The character name. Please refer to getNamedCharacter()
        to see what is available.
        """
        self.writeData(self.getNamedCharacter(name))

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
        self.writeCommand(self.LCD_HOME)
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

    def setBrightness(self, brightness):
        """
        Sets brightness level (1-4).

        Noritake command: 7.7.2 - Brightness control

        :param brightness: 4 for 100%, 3 for 75%, 2 for 50%, and 1 for 25%.
        """
        # This function is implemented in the 'noritake_cu_gpio.py' file.
        # For the I2C connection it has no effect.
        pass

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

    # .-----------------------------------------------------.
    # |                  HELPER FUNCTIONS                   |
    # '-----------------------------------------------------'

    def getNamedCharacter(self, name):
        """
        Returns a hex code of the named character.

        Named characters are special ones that can be used to display
        arrows, circles, icons-looking characters, etc.

        :param name: The name of the character.

        :return: A hex code of the named character if found, otherwise 0x3f (?).
        """
        characters = {
            # 00-0f - Custom characters.
            # 10-1f - Blocks, signs and triangles.
            'block_left_1': 0x10,
            'block_left_2': 0x11,
            'block_left_3': 0x12,
            'block_left_4': 0x13,
            'block_full': 0x14,
            'block_right_4': 0x15,
            'block_right_3': 0x16,
            'block_right_2': 0x17,
            'block_right_1': 0x18,
            'note': 0x19,
            'deg_c': 0x1a,
            'deg_f': 0x1b,
            'triangle_down': 0x1c,
            'triangle_right': 0x1d,
            'triangle_left': 0x1e,
            'triangle_up': 0x1f,
            # 20-2f - Standard special characters.
            # 30-3f - Digits and standard special characters.
            # 40-4f - @ and uppercase letters.
            # 50-5f - Uppercase letters and standard special characters.
            # 60-6f - Angled apostrophe-like character and lowercase letters.
            # 70-7f - Lowercase letters, standard special characters and arrows.
            'arrow_right': 0x7e,
            'arrow_left': 0x7f,
            # 80-8f - Accented letters and 4 characters (2 present on keyboard).
            'not_equal': 0x8d,
            'paragraph': 0x8f,
            # 90-9f.
            'circle_fill': 0x94,
            'circle_stroke': 0x95,
            'square_fill': 0x96,
            'square_stroke': 0x97,
            'broken_pipe': 0x98,
            'graph': 0x9a,
            'less_equal': 0x9b,
            'more_equal': 0x9c,
            'return': 0x9d,
            'arrow_up': 0x9e,
            'arrow_down': 0x9f,
            # a0-af.
            'square_bottom': 0xa1,
            'corner_top': 0xa2,
            'corner_bottom': 0xa3,
            'dot': 0xa5,
            'low_i': 0xaa,
            'hook': 0xad,
            'inverted_e': 0xae,
            'fork': 0xaf,
            # b0-bf.
            'high_i': 0xb4,
            'box_open': 0xba,
            # c0-cf.
            # d0-df.
            'triple_line': 0xd0,
            'box_closed': 0xdb,
            'box_open2': 0xdc,
            'slide': 0xdd,
            'shine': 0xde,
            'square_top': 0xdf,
            # e0-ef.
            'square_root': 0xe8,
            'hammer': 0xe9,
            'star': 0xeb,
            'cent': 0xec,
            'branch': 0xed,
            # f0-ff.
            'dash_x': 0xf8,
            'storage': 0xfc,
            'division': 0xfd,
        }

        if name in characters:
            return characters[name]
        else:
            # If no character then return '?'
            return 0x3f
