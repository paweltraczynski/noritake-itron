import time

# Import threading (platform-dependent).
threading_api = None

try:
    # CPython.
    import threading
    threading_api = 'threading'

except ImportError:
    # MicroPython.
    try:
        import _thread
        threading_api = '_thread'

    # Import error.
    except ImportError:
        raise ImportError('Noritake GU library requires either CPython threading or MicroPython _thread.')

class NoritakeGu:
    """
    Noritake GU series VFD driver for Raspberry Pi.

    Works on MicroPython and CPython.

    Example supported models are:
    - GU128X64
    - GU256X64
    - GU256X128

    :param bus: Serial UART or NoritakeParallel object. Needs write() method
    :param serial: True if the bus is a serial UART. False if bus is a NoritakeParallel object.
    :param width: Width of the screen in pixels. Default is 256.
    :param height: Height of the screen in pixels. Default is 64.
    """

    def __init__(self, bus, serial = False, width = 256, height = 64):
        self.bus = bus
        self.serial = serial

        # Define pixel dimensions of the screen.
        self.vfd_x_pixels = width
        self.vfd_y_pixels = height
        self.vfd_x_center = self.vfd_x_pixels // 2
        self.vfd_y_center = self.vfd_y_pixels // 2

        # Because the controller handles data in 8-bit bytes, it divides
        # the height into horizontal strips, called pages.
        self.vfd_y_pages = self.vfd_y_pixels // 8

        # Track currently selected font size and character table.
        # These are being updated in fontSize() and characterTable().
        # Functions drawText() and encodeText() rely on these values.
        self.vfd_font_size_current = 1
        self.vfd_char_table_current = 'Katakana'

        # Define all available font sizes.
        self.vfd_font_sizes = {
            1: {
                # Default font size is 6 x 8.
                'hex': 0x01,
                'width': 6,
                'height': 8,
                'x_chars': self.vfd_x_pixels // 6,
                'y_chars': self.vfd_y_pixels // 8,
            },
            2: {
                'hex': 0x02,
                'width': 8,
                'height': 16,
                'x_chars': self.vfd_x_pixels // 8,
                'y_chars': self.vfd_y_pixels // 16,
            },
            3: {
                'hex': 0x03,
                'width': 16,
                'height': 16,
                'x_chars': self.vfd_x_pixels // 16,
                'y_chars': self.vfd_y_pixels // 16,
            },
            4: {
                'hex': 0x04,
                'width': 16,
                'height': 32,
                'x_chars': self.vfd_x_pixels // 16,
                'y_chars': self.vfd_y_pixels // 32,
            },
            5: {
                'hex': 0x05,
                'width': 32,
                'height': 32,
                'x_chars': self.vfd_x_pixels // 32,
                'y_chars': self.vfd_y_pixels // 32,
            },
            6: {
                'hex': 0x06,
                'width': 12,
                'height': 24,
                'x_chars': self.vfd_x_pixels // 12,
                'y_chars': self.vfd_y_pixels // 24,
            },
        }

        # Track current window id.
        self.vfd_windows = [0]
        self.vfd_current_window = 0

        # Track scrolling texts.
        self.vfd_scrolling_texts = {}

        # Track current screen id.
        # This is used by initDualScreen() and switchScreen() methods.
        self.vfd_current_screen = 1

        # Track lengths of drawn texts. This is used for erasing previously
        # drawn text when a new text is being printed at the same position.
        # This assumes that at a given position the text size is not changed
        # after it was first time printed because the new text will use spaces
        # to cover the earlier text, and thus the font size needs to remain.
        self.drawn_texts = {}

        # Threading compatibility functions (MicroPython, CPython).
        self.thread_lock = False
        self.thread_start = False

        # Bus lock forces main thread script to wait before sending commands
        # to the display if separate thread is currently sending its command.
        self.bus_lock = self.threadLock()

        # Bus busy flag is set by the main script and forces a separate threads
        # script to wait before sending commands to the display. Using this
        # method gives the main thread priority over the other threads.
        self.bus_busy = False

        #### Noritake Commands. ###

        # Navigation commands.
        self.cursor_left = 0x08
        self.cursor_right = 0x09
        self.cursor_down = 0x0a
        self.cursor_home = 0x0b
        self.cursor_return = 0x0d
        self.clear_display = 0x0c
        self.clear_line_cursor_left = 0x18
        self.clear_line_cursor_right = 0x19

        # General commands.
        self.set_brightness = bytes([0x1f, 0x58])
        self.init_display = bytes([0x1b, 0x40])
        self.set_cursor = bytes([0x1f, 0x24])
        self.cursor_display = bytes([0x1f, 0x43])

        # Character display commands.
        self.write_screen_mode_select = bytes([0x1f, 0x28, 0x77, 0x10])
        self.character_table_type = bytes([0x1b, 0x74])
        self.overwrite_mode = bytes([0x1f, 0x01])
        self.vertical_scroll_mode = bytes([0x1f, 0x02])
        self.horizontal_scroll_mode = bytes([0x1f, 0x03])
        self.font_size = bytes([0x1f, 0x28, 0x67, 0x01])
        self.font_bold = bytes([0x1f, 0x28, 0x67, 0x41])

        # Display action commands.
        self.wait_action = bytes([0x1f, 0x28, 0x61, 0x01])
        self.short_wait_action = bytes([0x1f, 0x28, 0x61, 0x02])
        self.scroll_display_action = bytes([0x1f, 0x28, 0x61, 0x10])
        self.blink_display_action = bytes([0x1f, 0x28, 0x61, 0x11])
        self.curtain_display_action = bytes([0x1f, 0x28, 0x61, 0x12])
        self.spring_display_action = bytes([0x1f, 0x28, 0x61, 0x13])
        self.random_display_action = bytes([0x1f, 0x28, 0x61, 0x14])
        self.display_onoff = bytes([0x1f, 0x28, 0x61, 0x40])
        self.display_auto_off_time = bytes([0x1f, 0x28, 0x61, 0x40, 0x11])

        # Image drawing commands.
        self.draw_dot = bytes([0x1F, 0x28, 0x64, 0x10])
        self.draw_line_box = bytes([0x1F, 0x28, 0x64, 0x11])
        self.print_image = bytes([0x1F, 0x28, 0x64, 0x21])
        self.draw_text = bytes([0x1F, 0x28, 0x64, 0x30])

        # General display commands.

        # Window display commands.
        self.window_select = bytes([0x1f, 0x28, 0x77, 0x01])
        self.window_define_cancel = bytes([0x1f, 0x28, 0x77, 0x02])

        ### Initialize the display. ###

        # Allow time for the display to become ready for receiving commands.
        time.sleep(1)
        self.initDisplay()

    # .-----------------------------------------------------.
    # |                  WRITING COMMANDS                   |
    # '-----------------------------------------------------'

    def write(self, value, set_busy = True):
        """
        Write function for sending data bytes to the display.

        Data being sent can be bytes, bytearray, integer, or string.
        If an integer is being sent, it is interpreted as a command.

        :param value: Data to send to the display.
        :param set_busy: True prevents background threads from sending commands
        while this command is being executed.
        """
        was_bus_busy = self.bus_busy

        if set_busy and not was_bus_busy:
            self.bus_busy = True

        try:
            with self.bus_lock:
                if isinstance(value, bytes) or isinstance(value, bytearray):
                    self.bus.write(value)

                elif isinstance(value, str):
                    self.bus.write(value.encode())

                elif isinstance(value, (list, tuple)):
                    self.bus.write(bytes(value))

                else:
                    self.bus.write(bytes([value]))
        finally:
            if set_busy and not was_bus_busy:
                self.bus_busy = False

    def writeText(self, value, set_busy = True):
        """
        Write-text function for sending non-string values as text.

        Use this function to send values like integers that should
        be shown on the display instead of being treated as commands.

        :param value: Data to send to the display.
        :param set_busy: True prevents background threads from sending commands
        while this command is being executed.
        """
        self.write(self.encodeText(str(value)), set_busy)

    # .-----------------------------------------------------.
    # |                 NAVIGATION COMMANDS                 |
    # '-----------------------------------------------------'

    def cursorLeft(self, amount = 1):
        """
        Moves the cursor to the left by a specified number of characters.

        This command affects the currently selected window.

        Noritake command: 4.7.2.2 - Backspace
        Code: 08.

        :param amount: By how many characters to move the cursor left.
        """
        command = bytearray()
        for _ in range(amount):
            command.append(self.cursor_left)
        self.write(command)

    def cursorRight(self, amount = 1):
        """
        Moves the cursor to the right by a specified number of characters.

        This command affects the currently selected window.

        Noritake command: 4.7.2.3 - Horizontal tab
        Code: 09.

        :param amount: By how many characters to move the cursor right.
        """
        command = bytearray()
        for _ in range(amount):
            command.append(self.cursor_right)
        self.write(command)

    def cursorDown(self, amount = 1):
        """
        Moves the cursor down by a specified number of lines.

        This command affects the currently selected window.

        Noritake command: 4.7.2.4 - Line feed
        Code: 0A.

        :param amount: By how many lines to move the cursor down.
        """
        command = bytearray()
        for _ in range(amount):
            command.append(self.cursor_down)
        self.write(command)

    def cursorHome(self):
        """
        Sends the cursor to the home position.

        This command affects the currently selected window.

        Noritake command: 4.7.2.5 - Home position
        Code: 0B.
        """
        self.write(self.cursor_home)

    def cursorReturn(self):
        """
        Moves the cursor to the start of the current line.

        This command affects the currently selected window.

        Noritake command: 4.7.2.6 - Carriage return
        Code: 0D.
        """
        self.write(self.cursor_return)

    def clearDisplay(self):
        """
        Clears the display and moves the cursor to the home position.

        This command affects the currently selected window.

        Noritake command: 4.7.2.7 - Display clear
        Code: 0C.
        """
        self.write(self.clear_display)

    def clearLine(self):
        """
        Clears the current line and moves the cursor to the line start.

        This command affects the currently selected window.

        Noritake command: 4.7.2.8 - Line clear
        Code: 18.
        """
        self.write(self.clear_line_cursor_left)

    def clearLineRight(self):
        """
        Clears the current line from the cursor to the line end.

        This command affects the currently selected window.

        Noritake command: 4.7.2.9 - Line end clear
        Code: 19.
        """
        self.write(self.clear_line_cursor_right)

    # .-----------------------------------------------------.
    # |                  GENERAL COMMANDS                   |
    # '-----------------------------------------------------'

    def setBrightness(self, brightness):
        """
        Sets brightness level (0-8).

        Noritake command: 4.7.4.1 - Brightness level setting
        Code: 1F, 58, n.

        :param brightness: Brightness level (0-8).
        """
        levels = {
            0: 0x10,# 00.0%
            1: 0x11,# 12.5%
            2: 0x12,# 25.0%
            3: 0x13,# 37.5%
            4: 0x14,# 50.0%
            5: 0x15,# 62.5%
            6: 0x16,# 75.0%
            7: 0x17,# 87.5%
            8: 0x18,# 100%
        }

        # Validate brightness level.
        if brightness not in levels:
            raise ValueError('Brightness level must be between 0 and 8.')

        command = bytearray(self.set_brightness)
        # Parameter 'n' - brightness level.
        command.append(levels[brightness])
        self.write(command)

    def initDisplay(self):
        """
        Initializes the display (returns settings to their default values).

        Noritake command: 4.7.4.2 - Initialize display
        Code: 1B, 40.
        """
        self.write(self.init_display)

    def setCursor(self, x, y):
        """
        Sets the cursor position.

        This command affects the currently selected window.

        Noritake command: 4.7.4.3 - Cursor set
        Code: 1F 24 xL xH yL yH.

        :param x: Cursor X position in 1-dot units
        :param y: Cursor Y position in 8-dot units.
        """
        command = bytearray(self.set_cursor)
        # Parameters 'xL xH yL yH' - cursor position.
        command.extend([
            self.lowByte(x),
            self.highByte(x),
            self.lowByte(y),
            self.highByte(y)
        ])
        self.write(command)

    def cursorDisplay(self, visible):
        """
        Sets cursor visibility on/off.

        This command affects the currently selected window.

        Noritake command: 4.7.4.4 - Cursor display on/off
        Code: 1F 43 n.

        :param visible: True for visible, false for invisible.
        """
        command = bytearray(self.cursor_display)
        # Parameter 'n' - cursor display on/off byte.
        if visible:
            command.append(0x01)
        else:
            command.append(0x00)
        self.write(command)

    # .-----------------------------------------------------.
    # |             CHARACTER DISPLAY COMMANDS              |
    # '-----------------------------------------------------'

    def writeModeSelect(self, mode):
        """
        Selects the write screen mode to use.

        Noritake command: 4.7.4.5 - Write screen mode select
        Command: 1F, 28, 77, 10, a.

        :param mode: Pass either:
            - 0: for writing to the displayed area only
            - 1: for writing to the whole screen area (displayed and hidden).
        """
        command = bytearray(self.write_screen_mode_select)
        # Parameter 'a' - write screen mode.
        command.append(mode)
        self.write(command)

    # International font select.

    def characterTable(self, table):
        """
        Selects the character table to use.

        Characters already displayed are not affected.

        Noritake command: 4.7.4.7 - Character table type
        Command: 1B, 74, n.

        :param table: The character set to use (0-6, 11-13, 'user').
        """
        # All character sets contain ASCII characters at low bytes (0-127).
        # Each set contains additional characters at high bytes (128-255).
        sets = {
            # PC437 - USA, European.
            # USA/Western Europe characters, mathematical symbols,
            # and basic terminal line-drawing blocks.
            0: 0x00,
            # Katakana - Japanese.
            # Katakana phonetic characters and basic Japanese punctuation.
            1: 0x01,
            # PC850 - Multilingual Latin 1.
            # Replaces terminal box-drawing symbols from PC437 with additional
            # accented letters for Western European languages (Spanish, French,
            # German, Italian).
            2: 0x02,
            # PC860 - Portuguese.
            # Modified version of PC437 optimized specifically for Portuguese
            # and some Spanish-accented characters.
            3: 0x03,
            # PC863 - Canadian-French.
            # Optimized layout for Canadian-French, containing specific
            # characters and accent combinations used in Quebec.
            4: 0x04,
            # PC865 - Nordic.
            # Tailored for Nordic languages (Danish, Norwegian, Swedish,
            # Finnish). Swaps a few symbols from PC437 to regional letters.
            5: 0x05,
            # WPC1250 - Windows-1250.
            # Windows-1250 standard for Central European languages (Polish,
            # Czech, Slovak, Hungarian, Slovenian, Croatian, Bosnian, Serbian,
            # Montenegrin, Albanian, Romanian).
            6: 0x06,
            # PC866 - Cyrillic.
            # Maps the entire high block to alphabets using Cyrillic characters.
            11: 0x11,
            # PC852 - Latin 2.
            # Latin 2 standard for Central and Eastern Europe. Fully supports
            # Polish, Czech, Slovak, Hungarian, Slovenian, Croatian, Bosnian,
            # Serbian, Montenegrin, Albanian, Romanian, Kashubian, Silesian,
            # Sorbian.
            12: 0x12,
            # PC858 - Latin 1 with Euro currency symbol.
            # Identical to PC850 but modifies one slot (0xD5) to include
            # the official Euro currency symbol.
            13: 0x13,
            # User table.
            # Custom font block. Configures the display to use user-definable
            # custom character shapes uploaded manually into the VFD RAM.
            'user': 0xFF,
        }

        # Validate table parameter.
        if table not in sets:
            raise ValueError('Character table set must be one of: 0-6, 11-13, user.')

        # Keep track of the current character table by name.
        table_names = {
            0: 'PC437',
            1: 'Katakana',
            2: 'Latin 1',
            3: 'Portuguese',
            4: 'Canadian-French',
            5: 'Nordic',
            6: 'Windows 1250',
            11: 'Cyrillic',
            12: 'Latin 2',
            13: 'Latin 1 with Euro sign',
            'user': 'User'
        }
        self.vfd_char_table_current = table_names[table]

        command = bytearray(self.character_table_type)
        # Parameter 'n' - character table type byte.
        command.append(sets[table])
        self.write(command)

    def characterMode(self, mode):
        """
        Sets character write mode.

        This command affects the currently selected window.

        Noritake command: 4.7.4.8 - Overwrite mode
        Noritake command: 4.7.4.9 - Vertical scroll mode
        Noritake command: 4.7.4.10 - Horizontal scroll mode
        Code: 1F 01.

        :param mode: Pass 'overwrite', 'horizontal_scroll', or 'vertical_scroll'.
        """
        modes = {
            'overwrite': self.overwrite_mode,
            'horizontal_scroll': self.horizontal_scroll_mode,
            'vertical_scroll': self.vertical_scroll_mode,
        }

        if mode not in modes:
            raise ValueError('Mode must be one of: overwrite, horizontal_scroll, vertical_scroll.')

        self.write(modes[mode])

    # Horizontal scroll mode scroll on.
    # Horizontal scroll speed.

    def fontSize(self, size):
        """
        Selects font size: 1 (6x8), 2 (8x16), 3 (16x16), 4 (16x32), 5(32x32), 6(12x24).

        Noritake command: 4.7.4.13 - Font size select
        Code: 1F 28 67 01 m.

        :param size: The font size preset to use (1-4).
        """
        if size not in self.vfd_font_sizes:
            raise ValueError('Font size must be between 1 and 6.')

        # Keep track of the current font size.
        self.vfd_font_size_current = size

        command = bytearray(self.font_size)
        # Parameter 'm' - font size select byte.
        command.append(self.vfd_font_sizes[size]['hex'])
        self.write(command)

    # 2-byte character.
    # 2-byte character type.
    # Font width.
    # FROM extended font.
    # Font magnification.

    def fontBold(self, bold):
        """
        Sets font bold or cancels it.

        Noritake command: 4.7.4.19 - Bold character
        Code: 1F 28 67 41 b.

        :param bold: True to enable bold font, false to disable it.
        """
        command = bytearray(self.font_bold)
        # Parameter 'b' - bold on or off byte.
        command.append(0x01 if bold else 0x00)
        self.write(command)

    # .-----------------------------------------------------.
    # |               DISPLAY ACTION COMMANDS               |
    # '-----------------------------------------------------'

    def actionWait(self, t):
        """
        Causes the display to pause command and data processing
        for a specified time.

        Noritake command: 4.7.4.20 - Wait
        Code: 1F 28 61 01 t.

        :param t: Wait time multiplier (value * 0.5s, 0-255).
        """
        # Ensure the wait time value fits into a single byte range (0-255).
        t = max(0, min(int(t), 255))

        command = bytearray(self.wait_action)
        # Parameter 't' - wait time duration.
        command.append(t)

        self.write(command)

    def actionShortWait(self, t):
        """
        Causes the display to pause command and data processing
        for a short specified time based on the module's internal timing unit.

        Noritake command: 4.7.4.21 - Short Wait
        Code: 1F 28 61 02 t.

        :param t: Wait time multiplier (value * module timing unit, 0-255).
        """
        # Ensure the wait time value fits into a single byte range (0-255).
        t = max(0, min(int(t), 255))

        command = bytearray(self.short_wait_action)
        # Parameter 't' - wait time duration.
        command.append(t)

        self.write(command)

    def actionScroll(self, shift, cycles, speed):
        """
        Triggers a scroll display action that shifts the display area.

        Example usage to scroll the entire 256px * 64px screen:
        - The screen has 256 x-pixels * 8 bytes (64 y-pixels)
        - Total screen bytes are then 2048.
        - To shift the entire screen, we can animate shifts by 8 x-pixels
        - 256 / 8 = 32 shifts to shift the entire screen.
        - So the function call would be:
        - actionScroll(shift=8, cycles=32, speed=5)
        - The speed can be adjusted to taste.

        Noritake command: 4.7.4.22 - Scroll display action
        Code: 1F 28 61 10 wL wH cL cH s.

        :param shift: Display screen shift byte count.
            This is the number of bytes to shift the display area:
            - To shift the screen by 10 pixels: 10 * self.vfd_y_pages.
            - To shift the entire screen: self.vfd_x_pixels * self.vfd_y_pages.
        :param cycles: Number of scroll cycles.
            If set to more than 1 will cause the scrolling to repeat,
            which can be used in conjunction with a low shift value
            to create a shifting animation.
        :param speed: The scroll speed value 0-255.
            The actual speed is calculated using the formula:
            scrolling speed = speed * module timing unit (13-15ms) / shift.
        """
        # Speed integer must be single byte range (value 0-255).
        speed &= 0xFF

        command = bytearray(self.scroll_display_action)
        command.extend([
            # Parameters wL and wH - display screen shift byte count.
            self.lowByte(shift), self.highByte(shift),
            # Parameters cL and cH - number of cycles.
            self.lowByte(cycles), self.highByte(cycles),
            # Parameter 's' - scroll speed.
            speed
        ])
        self.write(command)

    def actionBlink(self, pattern, time_normal, time_blink, count = 0):
        """
        Triggers a blink display action, used for visual warnings or alerts.

        Noritake command: 4.7.4.23 - Blink display action
        Code: 1F 28 61 11 p t1 t2 c.

        :param pattern: Blink mode string: 'stop', 'blink', or 'invert'
        :param time_normal: Duration of the normal phase (value * 14.3ms, 1-255)
        :param time_blink: Duration of the blink phase (value * 14.3ms, 1-255)
        :param count: Number of blink cycles (1-255, or 0 for infinite loop).
        """
        # Map human-readable pattern names to byte values.
        pattern_map = {
            'stop': 0x00,
            'blink': 0x01,
            'invert': 0x02
        }

        if pattern not in pattern_map:
            raise ValueError("Pattern must be 'stop', 'blink', or 'invert'.")

        # Ensure timings and count fit into a single byte range (0-255).
        time_normal = max(0, min(int(time_normal), 255))
        time_blink = max(0, min(int(time_blink), 255))
        count = max(0, min(int(count), 255))

        command = bytearray(self.blink_display_action)
        command.extend([
            # Parameter 'p' - blink pattern.
            pattern_map[pattern],
            # Parameters t1 and t2 - normal display and blank/reverse display time.
            time_normal, time_blink,
            # Parameter 'c' - number of cycles.
            count
        ])

        self.write(command)

    def actionCurtain(self, direction, speed, pattern = 'blank'):
        """
        Triggers curtain display action, a transition effect.

        This command only affects the display area.
        The non-display area memory is not affected.

        Noritake command: 4.7.4.24 - Curtain display action
        Code: 1F 28 61 12 v s p.

        :param direction: Direction of curtain action:
            Pass 'right' (Left to Right), 'left' (Right to Left),
            'split' (Center to Outwards), or 'merge' (Outwards to Center).
        :param speed: Curtain action speed (0-255). 0 is fastest.
        :param pattern: Curtain action pattern.
            Pass string 'blank' (0x00), 'fill' (0xFF), or a raw integer mask (0-255).
        """
        # Map human-readable direction names to single byte.
        direction_map = {
            'right': 0x00,
            'left':  0x01,
            'split': 0x02,
            'merge': 0x03
        }

        if direction not in direction_map:
            raise ValueError("Direction must be 'right', 'left', 'split', or 'merge'.")

        # Map semantic pattern names to their corresponding byte values.
        if pattern == 'blank':
            pattern_value = 0x00
        elif pattern == 'fill':
            pattern_value = 0xFF
        else:
            # Fallback to the raw integer value passed by the user.
            pattern_value = int(pattern)

        # Ensure speed and pattern fit into a single byte range (0-255).
        speed = max(0, min(int(speed), 255))
        pattern_value = max(0, min(pattern_value, 255))

        command = bytearray(self.curtain_display_action)
        command.extend([
            # Parameter 'v' - curtain direction.
            direction_map[direction],
            # Parameter 's' - action speed.
            speed,
            # Parameter 'p' - curtain pattern byte.
            pattern_value
        ])

        self.write(command)

    def actionSpring(self, direction, speed, address):
        """
        Triggers spring display action, an elastic transition effect.

        This command stretches or compresses images from a specified memory address.

        Noritake command: 4.7.4.25 - Spring display action
        Code: 1F 28 61 13 v s pL pH.

        :param direction: Direction of spring action:
            Pass 'right' (Left to Right), 'left' (Right to Left),
            'split' (Center to Outwards), or 'merge' (Outwards to Center).
        :param speed: Spring action speed (0-255). 0 is fastest.
        :param address: 16-bit memory start address (0-65535) to source the image from.
        """
        # Map human-readable direction names to single byte.
        direction_map = {
            'right': 0x00,
            'left':  0x01,
            'split': 0x02,
            'merge': 0x03
        }

        if direction not in direction_map:
            raise ValueError("Direction must be 'right', 'left', 'split', or 'merge'.")

        # Ensure speed fits into a single byte range (0-255).
        speed = max(0, min(int(speed), 255))

        # Ensure address fits into a 16-bit range.
        address = max(0, min(int(address), 65535))

        command = bytearray(self.spring_display_action)
        command.extend([
            # Parameter 'v' - spring direction.
            direction_map[direction],
            # Parameter 's' - action speed.
            speed,
            # Parameters pL and pH - memory address in 16-bit Little-Endian format.
            self.lowByte(address),
            self.highByte(address)
        ])

        self.write(command)

    def actionRandom(self, speed, address):
        """
        Triggers random display action, a noise/melting transition effect.

        This command pulls pixels from a specified memory address and reveals
        them randomly on the screen in 8 discrete steps.

        Noritake command: 4.7.4.26 - Random display action
        Code: 1F 28 61 14 s pL pH.

        :param speed: Random action speed (0-255). 0 is fastest.
        :param address: 16-bit memory start address (0-65535) to source
            the image from.
        """
        # Ensure speed fits into a single byte range (0-255).
        speed = max(0, min(int(speed), 255))

        # Ensure address fits into a 16-bit range.
        address = max(0, min(int(address), 65535))

        command = bytearray(self.random_display_action)
        command.extend([
            # Parameter 's' - action speed.
            speed,
            # Parameters pL and pH - memory address in 16-bit Little-Endian format.
            self.lowByte(address),
            self.highByte(address)
        ])

        self.write(command)

    def displayOnOff(self, on_off):
        """
        Turns the display on, off or sets auto-off.

        Noritake command: 4.7.4.27 - Display power on/off/auto-off
        Code: 1F 28 61 40 p.

        :param on_off: Pass 'on', 'off' or 'auto-off'.
        """
        options = {
            'on': 0x01,
            'off': 0x00,
            'auto-off': 0x10,
        }

        # Validate on_off parameter.
        if on_off not in options:
            raise ValueError('On/off must be one of: on, off, auto-off.')

        command = bytearray(self.display_onoff)
        # Parameter 'p' - power on/off setting byte.
        command.append(options[on_off])
        self.write(command)

    def displayAutoOff(self, minutes):
        """
        Sets the display auto-off time (minutes, max 255).

        Noritake command: 4.7.4.28 - Display power auto-off time
        Code: 1F 28 61 40 11 t.

        :param minutes: Time in minutes.
        """
        # Validate 'minutes' parameter.
        if minutes < 0 or minutes > 255:
            raise ValueError('Minutes must be between 0 and 255.')

        command = bytearray(self.display_auto_off_time)
        # Parameter 't' - auto-off time.
        command.append(minutes)
        self.write(command)

    # .-----------------------------------------------------.
    # |               IMAGE DRAWING COMMANDS                |
    # '-----------------------------------------------------'

    def drawDot(self, pen, x, y):
        """
        Draws a dot on the display.

        Noritake command: 4.7.4.29 - Dot drawing
        Code: 1F 28 64 10 pen xL xH yL yH.

        :param pen: True to draw/set, false to erase/clear.
        :param x: X position of the dot
        :param y: Y position of the dot.
        """
        # Determine pen state: 0x01 for drawing, 0x00 for erasing.
        pen_hex = 0x01 if pen else 0x00

        # Ensure coordinates are within physical screen boundaries.
        x = self.rangeX(x)
        y = self.rangeY(y)

        command = bytearray(self.draw_dot)
        command.extend([
            # Parameter 'pen' - draw or erase.
            pen_hex,
            # Parameters xL xH yL yH - dot position.
            self.lowByte(x), self.highByte(x),
            self.lowByte(y), self.highByte(y),
        ])
        self.write(command)

    def drawLineBox(self, mode, pen, x1, y1, x2, y2):
        """
        Draws a line/box pattern from (x1, y1) to (x2, y2).

        Noritake command: 4.7.4.30 - Line/box pattern drawing.
        Code: 1F 28 64 11 mode pen x1L x1H y1L y1H x2L x2H y2L y2H.

        :param mode: What to draw ('line', 'box' or 'box_fill')
        :param pen: True to draw/set, false to erase/clear
        :param x1: Starting horizontal pixel coordinate (0 to 255)
        :param y1: Starting vertical pixel coordinate (0 to 63)
        :param x2: Ending horizontal pixel coordinate (0 to 255)
        :param y2: Ending vertical pixel coordinate (0 to 63).
        """
        modes = {
            'line': 0x00,
            'box': 0x01,
            'box_fill': 0x02,
        }

        # Validate mode parameter.
        if mode not in modes:
            raise ValueError('Mode must be one of: line, box, box_fill.')

        # Determine pen state: 0x01 for drawing, 0x00 for erasing.
        pen_hex = 0x01 if pen else 0x00

        # Ensure coordinates are within physical screen boundaries.
        x1 = self.rangeX(x1)
        y1 = self.rangeY(y1)
        x2 = self.rangeX(x2)
        y2 = self.rangeY(y2)

        command = bytearray(self.draw_line_box)
        command.extend([
            # Parameters 'mode' - line, box, or box_fill.
            modes[mode],
            # Parameter 'pen' - draw or erase.
            pen_hex,
            # Parameters x1L x1H y1L y1H x2L x2H y2L y2H.
            self.lowByte(x1), self.highByte(x1),
            self.lowByte(y1), self.highByte(y1),
            self.lowByte(x2), self.highByte(x2),
            self.lowByte(y2), self.highByte(y2)
        ])
        self.write(command)

    # Dot unit downloaded bit image display.
    # Dot unit real-time bit image display.

    def printImage(self, x, y, data):
        """
        Prints supplied image data at x and y position.

        Noritake command: 4.7.4.32 - Dot unit real-time bit image display
        Code: 1F 28 64 21 xPL xPH yPL yPH xL xH yL yH g d(1)...d(k)

        :param x: X position of the image
        :param y: Y position of the image
        :param data: The data of the image, including its size.
        """
        # Extract dimensions, which are the first 4 bytes.
        width = data[0] + (data[1] << 8)
        height = data[2] + (data[3] << 8)
        raw_pixels = data[4:]

        # Universal interleave logic.
        # 'num_rows' is how many bytes make up one vertical column.
        # Must be a multiple of 8.
        num_rows = (height + 7) // 8
        interleaved_data = []

        # Iterate through each column.
        for col in range(width):
            # For each column, we pick the byte from each 'stripe'.
            for row in range(num_rows):
                idx = (row * width) + col

                if idx < len(raw_pixels):
                    # Flip each 8-pixel segment vertically.
                    b = raw_pixels[idx]
                    b_reversed = 0
                    for i in range(8):
                        if b & (1 << i):
                            b_reversed |= (1 << (7 - i))

                    interleaved_data.append(b_reversed)

        # Send the command.
        command = bytearray(self.print_image)
        command.extend([
            # Parameters xPL xPH yPL yPH - position.
            self.lowByte(x), self.highByte(x),
            self.lowByte(y), self.highByte(y),
            # Parameters xL xH yL yH - size.
            self.lowByte(width), self.highByte(width),
            self.lowByte(height), self.highByte(height),
            # Parameter 'g' - display information (fixed 0x01).
            0x01
        ])
        # Set busy flag manually.
        try:
            self.bus_busy = True
            self.write(command, False)

            if self.serial:
                # Stability delay for serial connection at 38,400 baud rate.
                # 40 milliseconds (Micropython and CPython compatible).
                time.sleep(40 / 1000)

            # Send the interleaved data with throttling.
            for b in interleaved_data:
                self.write(bytes([b]), False)
                # Stability delay for serial connection at 38,400 baud rate.
                if self.serial:
                    # 3 microseconds (Micropython and CPython compatible).
                    time.sleep(3 / 1000000)

        finally:
            # Clear the busy flag manually after the image has been sent.
            self.bus_busy = False

    def drawText(self, x, y, text, clear = True):
        """
        Draws text at x and y position.

        Noritake command: 4.7.4.33 - Dot unit character display
        Code: 1F 28 64 30 xPL xPH yPL yPH m bLen d(1)...d(bLen).

        :param x: X position where the text will begin
        :param y: Y position where the text will begin
        :param text: The text to display
        :param clear: True to clear previous possibly longer text at this position.
        """
        # Ensure coordinates are within physical screen boundaries.
        x = self.rangeX(x)
        y = self.rangeY(y, False)

        # Make sure text is string.
        text = str(text)

        # Dynamically determine character limits based on the current font size.
        current_font = self.vfd_font_sizes[self.vfd_font_size_current]
        max_chars = max(1, (self.vfd_x_pixels - x) // current_font['width'])

        # Truncate and add ellipsis if text exceeds the current font's horizontal limit.
        if len(text) > max_chars:
            if max_chars >= 3:
                text = text[:max_chars - 3] + '...'
            else:
                text = text[:max_chars]

        # Text position id.
        position_id = f'{self.vfd_current_window}-{x}-{y}'

        # Text length in characters (used for tracking layout & clearing).
        current_length = len(text)

        # If the new text is shorter, calculate and append the required
        # number of spaces so that it fully covers the old text.
        if clear and (position_id in self.drawn_texts):
            previous_length = self.drawn_texts[position_id]

            if current_length < previous_length:
                spaces_count = previous_length - current_length
                text += ' ' * spaces_count

        # Save current text length.
        self.drawn_texts[position_id] = current_length

        # Encode string to bytes to precisely measure its length in bytes.
        # Do it using the self.encodeText() to allow for using non-ASCII characters.
        text_bytes = self.encodeText(text)
        bytes_length = len(text_bytes)

        if bytes_length > 255:
            raise ValueError('Text is too long; maximum encoded length is 255 bytes.')

        # Skip execution if the text is empty to save bus bandwidth.
        if bytes_length == 0:
            return

        # Mode parameter (0x00 = Normal overwrite mode).
        mode = 0x00

        command = bytearray(self.draw_text)
        command.extend([
            # Parameters xPL xPH yPL yPH - position.
            self.lowByte(x), self.highByte(x),
            self.lowByte(y), self.highByte(y),
            # Parameter 'm' - response select.
            mode,
            # Parameter 'bLen' - character data length.
            bytes_length,
        ])
        # Parameter 'd' - character data.
        command.extend(text_bytes)
        self.write(command)

    # Dot unit character display.
    # Real-time bit image display.
    # RAM bit image definition.
    # FROM bit image definition.
    # Downloaded bit image display.
    # Downloaded bit image scroll display.

    # .-----------------------------------------------------.
    # |              GENERAL DISPLAY COMMANDS               |
    # '-----------------------------------------------------'

    # Horizontal scroll display quality select.
    # Reverse display.
    # Write mixture display mode.

    # .-----------------------------------------------------.
    # |               WINDOW DISPLAY COMMANDS               |
    # '-----------------------------------------------------'

    def windowSelect(self, win_id, set_busy = True):
        """
        Selects a user window (1-4) or base window (0).

        Window position and window size are specified
        in units of one block (1×8 dots).

        Noritake command: 4.7.4.42 - Window select
        Code: 1F 28 77 01 a.

        :param win_id: The id of the window (1-4, or 0 for a base window)
        :param set_busy: True prevents background threads from sending commands
        while this command is being executed.
        """
        win_ids = {
            0: 0x00,
            1: 0x01,
            2: 0x02,
            3: 0x03,
            4: 0x04,
        }

        if win_id not in win_ids:
            raise ValueError('Window id must be between 0 and 4.')

        # Keep track of currently active window.
        if win_id in self.vfd_windows:
            self.vfd_current_window = win_id
        else:
            raise ValueError('The selected window does not exist.')

        command = bytearray(self.window_select)
        # Parameter 'a' - window id.
        command.append(win_ids[win_id])
        self.write(command, set_busy)

    def windowDefine(self, win_id, x, y, width, height):
        """
        Defines a user window on the display.

        Window position and window size are specified
        in units of one block (1×8 dots). This means that for 'y' and 'height'
        0 means pixels 0-7, 1 means pixels 8-15, 2 means pixels 16-23, etc.

        Noritake command: 4.7.4.43 - User window define/cancel
        Code: 1F 28 77 02 a b [xPL xPH yPL yPH xSL xSH ySL ySH].

        :param win_id: The id of the window (1-4)
        :param x: X position of the window, by 1 pixel
        :param y: Y position of the window, by 8 pixels
        :param width: Width of the window, by 1 pixel
        :param height: Height of the window, by 8 pixels.
        """
        win_ids = {
            1: 0x01,
            2: 0x02,
            3: 0x03,
            4: 0x04,
        }

        if win_id not in win_ids:
            raise ValueError('Window id must be between 1 and 4.')

        # Keep track of currently active window.
        if win_id not in self.vfd_windows:
            self.vfd_windows.append(win_id)

        # Ensure height is within physical screen boundaries.
        y = self.rangeY(y, True)

        # Ensure width and height can fit in the display.
        # Use vfd_x_pixels * 2 to allow writing also to the hidden area.
        max_width = (self.vfd_x_pixels * 2) - x
        max_height = self.vfd_y_pages - y

        width = max(1, min(width, max_width))
        height = max(1, min(height, max_height))

        command = bytearray(self.window_define_cancel)
        command.extend([
            # Parameter 'a' - window id.
            win_ids[win_id],
            # Parameter 'b' - set/cancel.
            0x01,
            # Parameters xPL xPH yPL yPH - position.
            self.lowByte(x), self.highByte(x),
            self.lowByte(y), self.highByte(y),
            # Parameters xSL xSH ySL ySH - size.
            self.lowByte(width), self.highByte(width),
            self.lowByte(height), self.highByte(height),
        ])
        self.write(command)

    def windowCancel(self, win_id):
        """
        Cancels a user window.

        Noritake command: 4.7.4.43 - User window define/cancel
        Code: 1F 28 77 02 a b [xPL xPH yPL yPH xSL xSH ySL ySH].

        :param win_id: The id of the window (1-4).
        """
        win_ids = {
            1: 0x01,
            2: 0x02,
            3: 0x03,
            4: 0x04,
        }

        if win_id == 0:
            raise ValueError('Base window 0 cannot be canceled.')

        if win_id not in self.vfd_windows:
            raise ValueError('The selected window does not exist.')

        # Keep track of currently active window.
        if win_id != 0 and win_id in self.vfd_windows:
            self.vfd_windows.remove(win_id)
            # Stop scrolling text in this window if there was any.
            self.scrollingTextStop(win_id)

        if self.vfd_current_window == win_id:
            self.vfd_current_window = 0

        command = bytearray(self.window_define_cancel)
        command.extend([
            # Parameter 'a' - window id.
            win_ids[win_id],
            # Parameter 'b' - set/cancel.
            0x00,
        ])
        self.write(command)

    # .-----------------------------------------------------.
    # |             DOWNLOAD CHARACTER COMMANDS             |
    # '-----------------------------------------------------'

    ### Download Character Setting Commands ###

    # Download character on/off.
    # Download character delete.
    # 16×16 Download character definition.
    # 16×16 Download character delete.
    # 32x32 Download character definition.
    # 32x32 Download character delete.
    # Download character save,
    # FROM user font definition.
    # FROM extension font definition.

    # .-----------------------------------------------------.
    # |              USER SETUP MODE COMMANDS               |
    # '-----------------------------------------------------'

    # User setup mode start.
    # User setup mode end.

    # .-----------------------------------------------------.
    # |                  I/O PORT COMMANDS                  |
    # '-----------------------------------------------------'

    # I/O port input/output setting.
    # I/O port output.
    # I/O port input.

    # .-----------------------------------------------------.
    # |                   MACRO COMMANDS                    |
    # '-----------------------------------------------------'

    # RAM macro define/delete
    # FROM macro define/delete
    # Macro execution.
    # Macro end condition.

    # .-----------------------------------------------------.
    # |                   OTHER COMMANDS                    |
    # '-----------------------------------------------------'

    # Memory SW setting.
    # Memory SW data sending.
    # General-purpose memory.
    # General-purpose memory transfer.
    # General-purpose memory send.
    # Display status send.
    # RS-232 serial settings.
    # Memory re-write mode.

    # .-----------------------------------------------------.
    # |                CUSTOM TEXT SCROLLING                |
    # '-----------------------------------------------------'

    def scrollingTextStart(self, win_id, win_width, text, font_size = 1, delay = 0.25, padding = 4):
        """
        Starts looped scrolling text animation in a selected window.

        Use this version if the text vertical position is dividable by 8 pixels.

        This version does rely on hardware windows which can only be
        positioned at multiples of 8 vertical Y pixels.

        :param win_id: The id of the window (1-4) to use for scrolling
        :param win_width: The pixel width of the window
        :param text: The text to scroll
        :param font_size: The font size (1-6)
        :param delay: Number of seconds to wait between scroll steps
        :param padding: How many spaces should be added after the text.
        """
        # Check if there is a window defined with this id.
        if win_id not in self.vfd_windows:
            return

        # Validate font size.
        if font_size not in self.vfd_font_sizes:
            raise ValueError('Font size must be between 1 and 6.')

        # If a scrolling text animation is already running with this id,
        # stop it first.
        self.scrollingTextStop(win_id)

        # Calculate max_chars that can fit into the pixel width.
        char_width = self.vfd_font_sizes[font_size]['width']
        max_chars = max(1, win_width // char_width)

        # Select the window and clear it.
        self.windowSelect(win_id)
        self.clearDisplay()

        # If text is empty or just spaces then exit after clearing.
        if not text or text.isspace():
            return

        # If the text fits, draw it once without animation.
        if len(text) <= max_chars:
            self.fontSize(font_size)
            self.write(self.encodeText(text))
            self.fontSize(1)
            return

        # Prepare the padded text loop.
        text_padded = text + (' ' * padding)
        text_len = len(text_padded)

        # Register the scrolling text by id.
        self.vfd_scrolling_texts[win_id] = True

        # Scrolling text loop.
        def scrolling_loop():
            index = 0
            first_frame = True

            while self.vfd_scrolling_texts.get(win_id, False):
                if not self.bus_busy:
                    # Get a slice of text with a fixed length.
                    text_slice = ''
                    for i in range(max_chars):
                        text_slice += text_padded[(index + i) % text_len]

                    # Update the display window content.
                    # Switch window before if needed.
                    previous_window = self.vfd_current_window
                    if self.vfd_current_window != win_id:
                        self.windowSelect(win_id)

                    self.fontSize(font_size)
                    self.clearDisplay()
                    self.write(self.encodeText(text_slice))
                    self.fontSize(1)

                    # Switch window after if needed.
                    if previous_window != win_id:
                        self.windowSelect(previous_window)

                    # Move the slice index by 1 character.
                    index = (index + 1) % text_len

                    # Wait a moment before the text starts scrolling.
                    if first_frame:
                        time.sleep(2)
                        first_frame = False
                    else:
                        time.sleep(delay)

                else:
                    time.sleep(delay)

        # Start the scrolling thread in the background.
        self.threadStart(scrolling_loop)

    def scrollingDrawTextStart(self, scroll_id, x, y, width, text, font_size = 1, delay = 0.25, padding = 4):
        """
        Starts looped scrolling text animation using drawText().

        Use this version if the text vertical Y position is not dividable
        by 8 pixels.

        This version does not rely on hardware windows which can only be
        positioned at multiples of 8 vertical Y pixels.

        Instead of using hardware windows for clipping the text,
        it clears the exact text rectangle once, then overwrites it with
        fixed-length text frames.

        Recommended id convention:
        - 1-4: window-based scrolling ids.
        - 5+: drawText-based scrolling ids.

        :param scroll_id: Unique id for this drawText scrolling animation
        :param x: X pixel position where the text starts
        :param y: Y pixel position where the text starts
        :param width: Pixel width available for the scrolling text
        :param text: The text to scroll
        :param font_size: The font size (1-6)
        :param delay: Number of seconds to wait between scroll steps
        :param padding: How many spaces should be added after the text.
        """
        # Validate font size.
        if font_size not in self.vfd_font_sizes:
            raise ValueError('Font size must be between 1 and 6.')

        # If a scrolling text animation is already running with this id,
        # stop it first.
        self.scrollingTextStop(scroll_id)

        # Calculate max_chars that can fit into the pixel width.
        char_width = self.vfd_font_sizes[font_size]['width']
        text_height = self.vfd_font_sizes[font_size]['height']
        max_chars = max(1, width // char_width)

        # Clear the text area.
        self.drawLineBox(
            'box_fill', False,
            x, y,
            x + width - 1,
            y + text_height - 1
        )

        # If text is empty or just spaces then exit after clearing.
        if not text or text.isspace():
            return

        # If the text fits, draw it once without animation.
        if len(text) <= max_chars:
            self.fontSize(font_size)
            self.drawText(x, y, text, False)
            self.fontSize(1)
            return

        # Prepare the padded text loop.
        text_padded = text + (' ' * padding)
        text_len = len(text_padded)

        # Register the scrolling text by id.
        self.vfd_scrolling_texts[scroll_id] = True

        # Scrolling text loop.
        def scrolling_loop():
            index = 0
            first_frame = True

            while self.vfd_scrolling_texts.get(scroll_id, False):
                if not self.bus_busy:
                    # Get a slice of text with a fixed length.
                    text_slice = ''
                    for i in range(max_chars):
                        text_slice += text_padded[(index + i) % text_len]

                    self.fontSize(font_size)
                    self.drawText(x, y, text_slice, False)
                    self.fontSize(1)

                    # Move the slice index by 1 character.
                    index = (index + 1) % text_len

                    # Wait a moment before the text starts scrolling.
                    if first_frame:
                        time.sleep(2)
                        first_frame = False
                    else:
                        time.sleep(delay)

                else:
                    time.sleep(delay)

        # Start the scrolling thread in the background.
        self.threadStart(scrolling_loop)

    def scrollingTextStop(self, scroll_id):
        """
        Stops a looped scrolling text animation.

        :param scroll_id: The id of the scrolling text to stop.
        """
        if scroll_id in self.vfd_scrolling_texts:
            # Setting this to false breaks the while loop in scrolling_loop().
            self.vfd_scrolling_texts[scroll_id] = False

    def scrollingTextStopAll(self):
        """
        Stops all looped scrolling text animations.

        Useful before exiting the main script on Raspberry Pi Pico, because
        MicroPython _thread does not provide a safe way to force-kill a thread.
        """
        for scroll_id in self.vfd_scrolling_texts:
            self.vfd_scrolling_texts[scroll_id] = False

    def busBusySet(self, window = 0):
        """
        Sets the busy flag to prevent scrolling text threads from writing.

        :param window: Pass an id of a window in which to write data.
        """
        # Set the busy flag.
        self.bus_busy = True

        # Select the window to write to.
        if self.vfd_current_window != window:
            self.windowSelect(window, False)

    def busBusyCancel(self):
        """
        Cancels the busy flag, allowing scrolling text threads to write again.
        """
        self.bus_busy = False

    # .-----------------------------------------------------.
    # |                 CUSTOM DUAL SCREEN                  |
    # '-----------------------------------------------------'

    def initDualScreen(self):
        """
        Initializes the dual-screen (double buffering).

        To write to screen 1, write to window 1.
        To write to screen 2, write to window 2.
        To change the active screen, use action.

        Cancels previous windows if they exist to completely reset memory.
        Defines Window 1 in the Display Area (X=0, 256x64 px).
        Defines Window 2 in the Hidden Area (X=256, 256x64 px).
        Sets the active window back to Window 1.

        How to use this:
        initDualScreen()
        # Write to screen 1 (Window 1), then select Window 2.
        windowSelect(2)
        # Write to screen 2 (Window 2).
        # Then switch the screen to show the contents of Window 2.
        switchScreen()
        """
        # Enable writing to the whole screen area (displayed + hidden).
        self.writeModeSelect(1)

        # Cancel previous window 1 and 2 if they exist.
        if 1 in self.vfd_windows:
            self.windowCancel(1)
        if 2 in self.vfd_windows:
            self.windowCancel(2)

        width = self.vfd_x_pixels
        height = self.vfd_y_pages

        # Create window 1 used as the display area.
        self.windowDefine(1, 0, 0, width, height)

        # Create window 2 used as the hidden area.
        self.windowDefine(2, width, 0, width, height)

        # Set the active writing to Window 1.
        self.windowSelect(1)
        self.vfd_current_screen = 1

        # Revert write mode to normal.
        # This is needed to write to the window 1 screen and window 2 screen
        # correctly.
        self.writeModeSelect(0)

    def switchScreenScroll(self, cycles = 32, speed = 1):
        """
        Switches the display content between the display area and
        the hidden area using a scroll display action.

        See actionScroll() for an explanation of parameters.

        :param cycles: Number of scroll cycles.
        :param speed: The scroll speed value 0-255.
        """
        # Validate cycles.
        if cycles < 1 or cycles > 255:
            raise ValueError('Cycles must be between 1 and 255')


        shift_bytes = self.vfd_x_pixels * self.vfd_y_pages
        shift = shift_bytes // cycles

        # Trigger the scroll display action.
        self.actionScroll(shift, cycles, speed)

        # Track current screen.
        if self.vfd_current_screen == 1:
            self.vfd_current_screen = 2
        else:
            self.vfd_current_screen = 1

    def switchScreenCurtain(self, curtain_speed = 0, cover_pattern = 'fill', uncover_pattern = 'blank'):
        """
        Switches the display content between the display area and
        the hidden area using a curtain display action.

        Warning: This method clears the current display area before switching.
        The curtain effect overwrites current screen content.
        After the switch, the original content has to be written back
        to the display before the user can switch back to it.

        See actionCurtain() for an explanation of parameters.

        :param curtain_speed: Curtain action speed (0-255). 0 is fastest.
        :param cover_pattern: The pattern used to cover the screen.
        :param uncover_pattern: The pattern used to reveal the new screen.
        """
        # Trigger the covering curtain from the edges to the center.
        self.actionCurtain('merge', curtain_speed, cover_pattern)

        # Trigger the uncovering curtain from the center to the edges.
        self.actionCurtain('split', curtain_speed, uncover_pattern)

        # Execute an instant screen switch by running
        # a 1-cycle scroll with zero speed.
        self.switchScreenScroll(1, 0)

    def switchScreenSpring(self, direction = 'split', speed = 2):
        """
        Switches the display content between the display area and
        the hidden area using spring display action.

        Warning: This method overwrites the current display area with content
        taken from the hidden area.
        After the switch, the original content has to be written back
        to the display hidden area before the user can switch back to it.

        See actionSpring() for an explanation of parameters.

        :param direction: Direction of spring action. Default is 'split'.
        :param speed: Spring action speed (0-255). 0 is fastest.
        """
        # Calculate the size of a single fullscreen buffer in bytes.
        screen_size_bytes = self.vfd_x_pixels * self.vfd_y_pages

        # Automatically determine the target hardware memory address.
        if self.vfd_current_screen == 1:
            target_address = screen_size_bytes
        else:
            target_address = 0

        # Trigger the spring display action.
        self.actionSpring(direction, speed, target_address)

        # Because the spring display action replaces the display area content
        # with the hidden area content, we end up having two identical contents
        # in both the display area and the hidden area. Jump to the other area
        # now, so there is an actual screen switch.
        # The original screen will have to be written back to the
        # hidden area before the user can switch back.
        self.switchScreenScroll(1, 0)

    def switchScreenRandom(self, speed = 2):
        """
        Switches the display content between the display area and
        the hidden area using random display action (melting transition effect).

        Warning: This method overwrites the current display area with content
        taken from the hidden area.
        After the switch, the original content has to be written back
        to the hidden area before the user can switch back to it.

        See actionRandom() for an explanation of parameters.

        :param speed: Random action speed (0-255). 0 is fastest.
        """
        # Calculate the size of a single fullscreen buffer in bytes.
        screen_size_bytes = self.vfd_x_pixels * self.vfd_y_pages

        # Automatically determine the target hardware memory address.
        if self.vfd_current_screen == 1:
            target_address = screen_size_bytes
        else:
            target_address = 0

        # Execute the random action.
        self.actionRandom(speed, target_address)

        # Because the random display action replaces the display area content
        # with the hidden area content, we end up having two identical contents
        # in both the display area and the hidden area. Jump to the other area
        # now, so there is an actual screen switch.
        # The original screen will have to be written back to the
        # hidden area before the user can switch back.
        self.switchScreenScroll(1, 0)

    # .-----------------------------------------------------.
    # |                  HELPER FUNCTIONS                   |
    # '-----------------------------------------------------'

    def lowByte(self, value):
        """
        Returns the lower 8 bits of a 16-bit integer.

        This VFD has a 15Bit address structure (0x00 ~ 0x1ff)
        This function returns the lower 8 bits.

        :param value: The value to convert.

        :return: The lower 8 bits of the value.
        """
        return value & 0xFF

    def highByte(self, value):
        """
        Returns the upper 8 bits of a 16-bit integer.

        This VFD has a 15Bit address structure (0x00 ~ 0x1ff)
        This function returns the upper 5 bits.

        :param value: The value to convert.

        :return: The upper 8 bits of the value.
        """
        return (value >> 8) & 0xFF

    def rangeX(self, x):
        """
        Keeps x within the horizontal pixel boundaries of the display.

        :param x: The x coordinate value to keep in the display area.

        :return: The x coordinate value within the display area.
        """
        # Coordinate rage is from 0.
        min_val = 0
        max_val = self.vfd_x_pixels - 1

        return max(min_val, min(x, max_val))

    def rangeY(self, y, pages = False):
        """
        Keeps y within the vertical pixel/page boundaries of the display.

        :param y: The y coordinate value to keep in the display area.
        :param pages: Pass true if counting y pages, or false if pixels.

        :return: The y coordinate/page value within the display area.
        """
        # Coordinate rage is from 0.
        min_val = 0
        max_val = (self.vfd_y_pages if pages else self.vfd_y_pixels) - 1

        return max(min_val, min(y, max_val))

    def transliteratePolish(self, text):
        """
        Converts polish characters to ASCII equivalents.

        :param text: The text to transliterate.
        :return: The transliterated text.
        """
        letters = {
            'Ą': 'A',
            'ą': 'a',
            'Ć': 'C',
            'ć': 'c',
            'Ę': 'E',
            'ę': 'e',
            'Ł': 'L',
            'ł': 'l',
            'Ń': 'N',
            'ń': 'n',
            'Ó': 'O',
            'ó': 'o',
            'Ś': 'S',
            'ś': 's',
            'Ź': 'Z',
            'ź': 'z',
            'Ż': 'Z',
            'ż': 'z',
        }

        return ''.join([letters.get(char, char) for char in str(text)])

    def encodeText(self, text):
        """
        Encodes extended ASCII characters so they can be displayed on the VFD.

        Characters 0 to 127 are regular ASCII, while the characters 128 to 255
        are the ones that can be enabled by calling the characterTable() method.

        This method processes the text character by character and returns
        a single-byte sequence compatible with the display.

        Currently, only Latin 1 and Latin 2 are supported.
        Other sets supported by the VFD can be added if needed.

        Example:
        no.characterTable('latin2')
        text = no.encodeText('Wyróżniać się', 'Latin2')
        no.write(text)
        """
        sets = {
            'PC437': {},
            'Katakana': {},
            'Latin 1': {
                # 0x80 - 0x8F
                'Ç': 0x80, 'ü': 0x81, 'é': 0x82, 'â': 0x83, 'ä': 0x84, 'à': 0x85,
                'å': 0x86, 'ç': 0x87, 'ê': 0x88, 'ë': 0x89, 'è': 0x8A, 'ï': 0x8B,
                'î': 0x8C, 'ì': 0x8D, 'Ä': 0x8E, 'Å': 0x8F,
                # 0x90 - 0x9F
                'É': 0x90, 'æ': 0x91, 'Æ': 0x92, 'ô': 0x93, 'ö': 0x94, 'ò': 0x95,
                'û': 0x96, 'ù': 0x97, 'ÿ': 0x98, 'Ö': 0x99, 'Ü': 0x9A, 'ø': 0x9B,
                '£': 0x9C, 'Ø': 0x9D, '×': 0x9E, 'ƒ': 0x9F,
                # 0xA0 - 0xAF
                'á': 0xA0, 'í': 0xA1, 'ó': 0xA2, 'ú': 0xA3, 'ñ': 0xA4, 'Ñ': 0xA5,
                'ª': 0xA6, 'º': 0xA7, '¿': 0xA8, '®': 0xA9, '¬': 0xAA, '½': 0xAB,
                '¼': 0xAC, '¡': 0xAD, '«': 0xAE, '»': 0xAF,
                # 0xB0 - 0xBF
                '░': 0xB0, '▒': 0xB1, '▓': 0xB2, '│': 0xB3, '┤': 0xB4, 'Á': 0xB5,
                'Â': 0xB6, 'À': 0xB7, '©': 0xB8, '╣': 0xB9, '║': 0xBA, '╗': 0xBB,
                '╝': 0xBC, '¢': 0xBD, '¥': 0xBE, '┐': 0xBF,
                # 0xC0 - 0xCF
                '└': 0xC0, '┴': 0xC1, '┬': 0xC2, '├': 0xC3, '─': 0xC4, '┼': 0xC5,
                'ã': 0xC6, 'Ã': 0xC7, '╚': 0xC8, '╔': 0xC9, '╩': 0xCA, '╦': 0xCB,
                '╠': 0xCC, '═': 0xCD, '╬': 0xCE, '¤': 0xCF,
                # 0xD0 - 0xDF
                'ð': 0xD0, 'Ð': 0xD1, 'Ê': 0xD2, 'Ë': 0xD3, 'È': 0xD4, 'ı': 0xD5,
                'Í': 0xD6, 'Î': 0xD7, 'Ï': 0xD8, '┘': 0xD9, '┌': 0xDA, '█': 0xDB,
                '▄': 0xDC, '¦': 0xDD, 'Ì': 0xDE, '▀': 0xDF,
                # 0xE0 - 0xEF
                'Ó': 0xE0, 'ß': 0xE1, 'Ô': 0xE2, 'Ò': 0xE3, 'õ': 0xE4, 'Õ': 0xE5,
                'µ': 0xE6, 'þ': 0xE7, 'Þ': 0xE8, 'Ú': 0xE9, 'Û': 0xEA, 'Ù': 0xEB,
                'ý': 0xEC, 'Ý': 0xED, '¯': 0xEE, '´': 0xEF,
                # 0xF0 - 0xFF
                '\xad': 0xF0, '±': 0xF1, '‗': 0xF2, '¾': 0xF3, '¶': 0xF4, '§': 0xF5,
                '÷': 0xF6, '¸': 0xF7, '°': 0xF8, '¨': 0xF9, '·': 0xFA, '¹': 0xFB,
                '³': 0xFC, '²': 0xFD, '■': 0xFE, '\xa0': 0xFF
            },
            'Portuguese': {},
            'Canadian-French': {},
            'Nordic': {},
            'Windows 1250': {},
            'Cyrillic': {},
            'Latin 2': {
                # 0x80 - 0x8F
                'Ç': 0x80, 'ü': 0x81, 'é': 0x82, 'â': 0x83, 'ä': 0x84, 'ů': 0x85,
                'ć': 0x86, 'ç': 0x87, 'ł': 0x88, 'ë': 0x89, 'Ő': 0x8A, 'ő': 0x8B,
                'î': 0x8C, 'Ź': 0x8D, 'Ä': 0x8E, 'Ć': 0x8F,
                # 0x90 - 0x9F
                'É': 0x90, 'Ĺ': 0x91, 'ĺ': 0x92, 'ô': 0x93, 'ö': 0x94, 'Ľ': 0x95,
                'ľ': 0x96, 'Ś': 0x97, 'ś': 0x98, 'Ö': 0x99, 'Ü': 0x9A, 'Ť': 0x9B,
                'ť': 0x9C, 'Ł': 0x9D, '×': 0x9E, 'č': 0x9F,
                # 0xA0 - 0xAF
                'á': 0xA0, 'í': 0xA1, 'ó': 0xA2, 'ú': 0xA3, 'Ą': 0xA4, 'ą': 0xA5,
                'Ž': 0xA6, 'ž': 0xA7, 'Ę': 0xA8, 'ę': 0xA9, '¬': 0xAA, 'ź': 0xAB,
                'Č': 0xAC, 'ş': 0xAD, '«': 0xAE, '»': 0xAF,
                # 0xB0 - 0xBF
                '░': 0xB0, '▒': 0xB1, '▓': 0xB2, '│': 0xB3, '┤': 0xB4, 'Á': 0xB5,
                'Â': 0xB6, 'Ě': 0xB7, 'Ş': 0xB8, '╣': 0xB9, '║': 0xBA, '╗': 0xBB,
                '╝': 0xBC, 'Ż': 0xBD, 'ż': 0xBE, '┐': 0xBF,
                # 0xC0 - 0xCF
                '└': 0xC0, '┴': 0xC1, '┬': 0xC2, '├': 0xC3, '─': 0xC4, '┼': 0xC5,
                'Ă': 0xC6, 'ă': 0xC7, '╚': 0xC8, '╔': 0xC9, '╩': 0xCA, '╦': 0xCB,
                '╠': 0xCC, '═': 0xCD, '╬': 0xCE, '¤': 0xCF,
                # 0xD0 - 0xDF
                'đ': 0xD0, 'Đ': 0xD1, 'Ď': 0xD2, 'Ë': 0xD3, 'ď': 0xD4, 'Ň': 0xD5,
                'Í': 0xD6, 'Î': 0xD7, 'ě': 0xD8, '┘': 0xD9, '┌': 0xDA, '█': 0xDB,
                '▄': 0xDC, 'Ţ': 0xDD, 'Ů': 0xDE, '▀': 0xDF,
                # 0xE0 - 0xEF
                'Ó': 0xE0, 'ß': 0xE1, 'Ô': 0xE2, 'Ń': 0xE3, 'ń': 0xE4, 'ň': 0xE5,
                'Š': 0xE6, 'š': 0xE7, 'Ŕ': 0xE8, 'Ú': 0xE9, 'ŕ': 0xEA, 'Ű': 0xEB,
                'ý': 0xEC, 'Ý': 0xED, 'ţ': 0xEE, '´': 0xEF,
                # 0xF0 - 0xFF
                '\xad': 0xF0, '˝': 0xF1, '˛': 0xF2, 'ˇ': 0xF3, '˘': 0xF4, '§': 0xF5,
                '÷': 0xF6, '¸': 0xF7, '°': 0xF8, '¨': 0xF9, '˙': 0xFA, 'ű': 0xFB,
                'Ř': 0xFC, 'ř': 0xFD, '■': 0xFE, '\xa0': 0xFF,
            },
            'Latin 1 with Euro sign': {},
            'User': {},
        }

        active_map = sets[self.vfd_char_table_current]
        output = bytearray()

        for char in text:
            code = ord(char)

            # Latin 2 characters.
            if char in active_map:
                output.append(active_map[char])
            # ASCII characters.
            elif code < 128:
                output.append(code)
            # Replace unsupported characters with a question mark.
            else:
                output.append(ord('?'))

        return bytes(output)

    # .-----------------------------------------------------.
    # |               COMPATIBILITY FUNCTIONS               |
    # '-----------------------------------------------------'

    def threadLock(self):
        """
        Creates a thread lock using the available platform API.

        :return: A new thread lock object.
        """
        if not self.thread_lock:
            if threading_api == 'threading':
                # CPython.
                self.thread_lock = threading.Lock

            elif threading_api == '_thread':
                # MicroPython.
                self.thread_lock = _thread.allocate_lock

            else:
                raise SystemExit('threadLock() error: neither threading nor _thread are available.')

        return self.thread_lock()

    def threadStart(self, function):
        """
        Starts a background thread using the available platform API.

        :param function: Function to run in the background thread.
        """
        if not self.thread_start:
            if threading_api == 'threading':
                # CPython.
                def start(function_name):
                    thread = threading.Thread(target = function_name)
                    thread.daemon = True
                    thread.start()

                self.thread_start = start

            elif threading_api == '_thread':
                # MicroPython.
                self.thread_start = lambda function_name: _thread.start_new_thread(function_name, ())

            else:
                raise SystemExit('threadStart() error: neither threading nor _thread are available.')

        self.thread_start(function)

