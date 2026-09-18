import time
import math

# Custom libs.
from noritake_gu import NoritakeGu
from hifi_display_icons import HiFiDisplayIcons

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
        raise ImportError('Display module requires either CPython threading or MicroPython _thread.')

class HiFiDisplay:
    """
    Intermediate class for the Noritake GU Hi-Fi specific commands.

    This class supports both MicroPython and CPython.

    CircuitPython is not supported yet.

    :param no: An instance of the NoritakeGu() class.
    """

    def __init__(self, no):
        self.no = no # type: NoritakeGu

        disp_icons = HiFiDisplayIcons()
        self.icons = disp_icons.iconsList()

        # Keep track of track data displayed on the screen.
        # This used to skip updating them when the value did not change.
        self.current_values = {
            # Track number.
            'track_display': '',
            'track_current': 0,
            'track_total': 0,
            # Track time.
            'time_display': '',
            'time_elapsed': 0,
            'time_total': 0,
            # Other.
            'volume': 0.0,
            'title': '',
            'artist': '',
            # Buttons (shown icons).
            'button_1': '',
            'button_2': '',
            'button_3': '',
            'button_4': '',
            'button_5': '',
            'button_6': '',
            'button_7': '',
        }

        # Enable dual screen.
        # The first screen is used for the main display.
        # The second screen is used for showing messages (volume level, etc.).
        self.no.initDualScreen()

        # Flag for locking the display while a message is shown.
        # When a message is shown, this flag is set to true.
        # When a message goes away, this flag is set to false.
        # When this flag is true, no other writes are performed to
        # the display, except for requests for showing other messages.
        # Example: Changing volume slowly shows new volume values as
        # consecutive messages, while all other writes and not performed.
        self.message_shown = False

        # Track when the message was shown to clear it after few seconds.
        self.message_time = 0
        self.message_watcher_running = False

        # Threading compatibility functions (MicroPython, CPython).
        self.thread_start = False

        # Static config.

        # Define volume bar width.
        # This variable is used for positioning of the volume bar,
        # the volume icon and the volume value.
        self.volume_bar_width = 54

        # For how long a message screen stays on before it goes away.
        self.message_timeout = 2

        # Time ticks_ms and ticks_diff compatibility variables.
        self.ticks_ms = False
        self.ticks_diff = False

    # .-----------------------------------------------------.
    # |                 PRINTING FUNCTIONS                  |
    # '-----------------------------------------------------'

    def printInitial(self):
        """
        Prints initial elements that are shown on startup.

        The printed elements are:
        - Volume indicator icon
        - Volume bar outer static rectangle
        - Button icons.
        """
        # Print volume indicator icon and volume bar outer static rectangle.
        vfd_width = self.no.vfd_x_pixels
        bar_width = self.volume_bar_width
        bar_start = (vfd_width // 2) - (bar_width // 2)
        bar_end = bar_start + bar_width
        icon_x = bar_start - 13

        self.no.busBusySet(1)
        self.no.printImage(icon_x, 0, self.icons['speaker'])
        self.no.drawLineBox('box', True, bar_start, 0, bar_end, 6)
        self.no.busBusyCancel()

        # Print button icons.
        self.printButtonIcon(1, 'play_prev')
        self.printButtonIcon(2, 'play_play')
        self.printButtonIcon(3, 'play_stop')
        self.printButtonIcon(4, 'play_next')
        self.printButtonIcon(5, 'volume_down')
        self.printButtonIcon(6, 'volume_up')
        self.printButtonIcon(7, 'power')

    def printTrack(self, current, total):
        """
        Prints the current track number on the display.

        :param current: Current track number.
        :param total: Total number of tracks.
        """
        # Return if a message screen is shown.
        if self.message_shown:
            return

        # Get the currently displayed track, format the new track.
        old_track = f"{self.current_values['track_display']}"
        new_track = f'{current}/{total}'

        # Update track info only if it has changed.
        if new_track == old_track:
            return

        # Create the final text by adding spaces at the end so that
        # it completely overwrites the previously displayed text.
        padded_track = self.padText(new_track, old_track)

        # Set busy flag and select the window.
        self.no.busBusySet(1)

        # Display track number.
        self.no.setCursor(0, 0)
        self.no.write(padded_track)

        # Cancel busy flag.
        self.no.busBusyCancel()

        # Save current value.
        self.current_values['track_display'] = new_track
        self.current_values['track_current'] = current
        self.current_values['track_total'] = total

    def printTime(self, elapsed, total):
        """
        Prints current track time on the display.

        :param elapsed: Track elapsed time in seconds.
        :param total: Total track time in seconds.
        """
        # Return if a message screen is shown.
        if self.message_shown:
            return

        # Get the currently displayed time.
        old_time = f"{self.current_values['time_display']}"

        # Format the new time.
        minutes = elapsed // 60
        seconds = elapsed % 60
        elapsed_formatted = f'{minutes}:{seconds:02d}'

        minutes = total // 60
        seconds = total % 60
        total_formatted = f'{minutes}:{seconds:02d}'

        new_time = f'{elapsed_formatted} {total_formatted}'

        # Update time info only if it has changed.
        if new_time == old_time:
            return

        # Create the final text by adding spaces at the end so that
        # it completely overwrites the previously displayed text.
        padded_time = self.padText(new_time, old_time, True)

        # Calculate track time x position.
        # Calculate cursor position from the right edge of the display.
        char_width = self.no.vfd_font_sizes[1]['width']
        time_width = len(padded_time) * char_width
        cursor_x = self.no.vfd_x_pixels - time_width

        # Set busy flag and select the window.
        self.no.busBusySet(1)

        # Display track time.
        self.no.setCursor(cursor_x, 0)
        self.no.write(padded_time)

        # Cancel busy flag.
        self.no.busBusyCancel()

        self.current_values['time_display'] = new_time
        self.current_values['time_elapsed'] = elapsed
        self.current_values['time_total'] = total

    def printVolume(self, percent):
        """
        Prints the currently set volume level on the display.

        :param percent: The volume level float value, 0.0 to 100.0.
        """
        # Return if a message screen is shown.
        if self.message_shown:
            return

        # Clamp the percentage to safe boundaries.
        percent = max(0.0, min(float(percent), 100.0))

        # Update volume info only if it changed.
        if self.current_values['volume'] == percent:
            return

        # Calculate the volume bar min and max x position.
        vfd_width = self.no.vfd_x_pixels
        bar_width = self.volume_bar_width
        bar_start = (vfd_width // 2) - (bar_width // 2)
        bar_end = bar_start + bar_width

        # Bar inner rectangle is smaller than the bar itself.
        bar_min = bar_start + 2
        bar_max = bar_end - 2
        bar_top = 0

        # Percent position.
        percent_pos = bar_end + 6

        # Calculate the volume bar top position based on the percentage.
        if percent != 0:
            if percent == 100:
                bar_top = bar_max
            else:
                # Standard linear mapping with truncation down.
                bar_add = int(percent * bar_width / 100.0)

                # Since at this point the percent is not zero, we need
                # to have at least one pixel in the volume bar.
                if bar_add == 0:
                    bar_add = 1

                bar_top = bar_min + bar_add

        # Prepare the old and new percent text.
        old_percent = f"{math.ceil(int(self.current_values['volume']))}"
        new_percent = f'{math.ceil(percent)}'

        # Create the final text by adding spaces to the end so that
        # it completely overwrites the previously displayed text.
        padded_percent = self.padText(new_percent, old_percent)

        # Set busy flag and select the window.
        self.no.busBusySet(1)

        # Clear previous volume bar if needed.
        if self.current_values['volume'] > percent:
            self.no.drawLineBox('box_fill', False, bar_min, 2, bar_max, 4)

        # Print the volume bar.
        self.no.drawLineBox('box_fill', True, bar_min, 2, bar_top, 4)

        # Print rounded percent.
        self.no.setCursor(percent_pos, 0)
        self.no.write(padded_percent)

        # Cancel busy flag.
        self.no.busBusyCancel()

        # Save current volume.
        self.current_values['volume'] = percent

    def printTitle(self, title):
        """
        Prints the current track title on the display as a scrolling text.

        :param title: The name of the track title to print on the display.
        """
        # Return if a message screen is shown.
        if self.message_shown:
            return

        # Update title only if it changed.
        if self.current_values['title'] == title:
            return

        # Set busy flag and select the window.
        self.no.busBusySet(1)

        self.no.fontSize(2)
        # The title encoding of non-ASCII characters is performed in the
        # drawText() function.
        self.no.scrollingDrawTextStart(5, 0, 14, self.no.vfd_x_pixels, title, 2, 0.16, 4)
        # Restore default font size.
        self.no.fontSize(1)

        # Cancel busy flag.
        self.no.busBusyCancel()

        # Save current value.
        self.current_values['title'] = title

    def printArtist(self, artist):
        """
        Prints current track artist on the display.

        :param artist: The name of the track artist to print on the display.
        """
        # Return if a message screen is shown.
        if self.message_shown:
            return

        # Update artist only if it changed.
        if self.current_values['artist'] == artist:
            return

        # Set busy flag and select the window.
        self.no.busBusySet(1)

        # The artist encoding of non-ASCII characters is performed in the
        # drawText() function.
        self.no.drawText(0, 36, artist)

        # Cancel busy flag.
        self.no.busBusyCancel()

        # Save current value.
        self.current_values['artist'] = artist

    def printButtonIcon(self, button, icon_key):
        """
        Prints the selected button icon on the display.

        :param button: The button position/slot at which to print the icon.
        :param icon_key: The icon key from which to get the image data to print.
        """
        # Return if a message screen is shown.
        if self.message_shown:
            return

        button_key = f'button_{button}'

        # Update the button icon only if it changed.
        if self.current_values[button_key] == icon_key:
            return

        x = 2
        y = 48

        if button == 1:
            x = 2
        elif button == 2:
            x = 30
        elif button == 3:
            x = 58
        elif button == 4:
            x = 86
        elif button == 5:
            x = 184
        elif button == 6:
            x = 212
        elif button == 7:
            x = 240

        # Set busy flag and select the window.
        self.no.busBusySet(1)

        self.no.printImage(x, y, self.icons[icon_key])

        # Cancel busy flag.
        self.no.busBusyCancel()

        # Save current value.
        self.current_values[button_key] = icon_key

    def printButtonAuto(self, icon_key):
        """
        Allows quick toggling of displayed button icons at their positions.

        :param icon_key: The icon key to pass to printButtonIcon().
        """
        # Return if a message screen is shown.
        if self.message_shown:
            return

        position = 0

        if icon_key == 'play_play':
            position = 2
        elif icon_key == 'play_pause':
            position = 2

        self.printButtonIcon(position, icon_key)

    # .-----------------------------------------------------.
    # |                  SPECIAL FUNCTIONS                  |
    # '-----------------------------------------------------'

    def redrawScreen(self):
        """
        Redraws the entire main screen after it was wiped.

        This function can be called after performing a curtain, spring, or
        random screen switch command that wipes the original screen.
        """
        values = self.current_values.copy()

        # Clear values so that they are reprinted.
        for key, value in self.current_values.items():
            if isinstance(value, int):
                self.current_values[key] = 0
            elif isinstance(value, float):
                self.current_values[key] = 0.0
            else:
                self.current_values[key] = ''

        # Reprint everything.
        self.no.clearDisplay()
        self.printInitial()
        self.printTrack(values['track_current'], values['track_total'])
        self.printTime(int(values['time_elapsed']), int(values['time_total']))
        self.printVolume(values['volume'])
        self.printTitle(values['title'])
        self.printArtist(values['artist'])
        # Currently, only the second button changes (play/pause).
        self.printButtonAuto(values['button_2'])

    # .-----------------------------------------------------.
    # |                  MESSAGE FUNCTIONS                  |
    # '-----------------------------------------------------'

    def showMessage(self, category, value):
        """
        Shows a message in a styled box using the second screen.

        While the message is shown, no other screen updates are performed.

        :param category: The type of message to show, like
            volume, bass, treble, balance, text.
        :param value: The value to use to construct the message.
        """
        # Prepare the text based on the category.
        if category == 'volume':
            message = f'Volume: {int(value)}'
        elif category == 'bass':
            message = f'Bass: {self.formatTone(value)}'
        elif category == 'treble':
            message = f'Treble: {self.formatTone(value)}'
        elif category == 'balance':
            message = f'Balance: {self.formatBalance(value)}'
        elif category == 'text':
            message = value
        else:
            return

        # Mark message mode as shown.
        self.message_shown = True

        # If this is the first message, extra commands are sent to the VFD.
        first_message = self.no.vfd_current_screen != 2
        target_window = 2 if first_message else 1

        # Set busy flag and select the window.
        self.no.busBusySet(target_window)

        try:
            # Define message box size and font size.
            # TOOD: Move these to inits config section.
            box_width = 160
            box_height = 32
            shadow_offset = 2
            font_size = 2

            # Fetch font metrics.
            font_metrics = self.no.vfd_font_sizes[font_size]
            char_width = font_metrics['width']

            # Calculate box starting coordinates for a centered box.
            # X and Y are counted from 0 for the 1st pixel, 1 for the 2nd, and so on.
            x1 = (self.no.vfd_x_pixels - box_width) // 2
            y1 = (self.no.vfd_y_pixels - box_height) // 2

            # Calculate box ending coordinates.
            # Decrease by -1px so that the right/bottom edges are within the box size.
            x2 = x1 + box_width - 1
            y2 = y1 + box_height - 1

            # Clamp the message to the maximum width so it fits within the box.
            text_max = (box_width - 10) // char_width
            if len(message) > text_max:
                message = message[:text_max - 2] + '..'

            # Calculate the total width of the text string in pixels.
            text_length = len(message)
            text_width = text_length * char_width

            # Calculate coordinates to center the text perfectly within the box.
            offset_x = (box_width - text_width) // 2
            cursor_x = x1 + offset_x
            cursor_y = (self.no.vfd_y_pages // 2) - 1

            # Save the message time.
            self.message_time = self.timeTicksMs()

            if first_message:
                self.no.clearDisplay()

                # Print the message box shadow and content area.
                self.no.drawLineBox(
                    'box_fill', True,
                    x1 + shadow_offset,
                    y1 + shadow_offset,
                    x2 + shadow_offset,
                    y2 + shadow_offset
                )

                # Print the message box content area.
                self.no.drawLineBox('box', True, x1, y1, x2, y2)

            # Clear the internal area inside the box.
            self.no.drawLineBox('box_fill', False, x1 + 1, y1 + 1, x2 - 1, y2 - 1)

            # Set cursor position and write the message.
            self.no.setCursor(cursor_x, cursor_y)
            self.no.fontSize(font_size)
            self.no.write(self.no.encodeText(message), False)
            self.no.fontSize(1)

            # Show the message.
            if first_message:
                self.no.switchScreenScroll(1, 0)

            if not self.message_watcher_running:
                self.message_watcher_running = True
                self.threadStart(self.messageWatcher)

        finally:
            self.no.busBusyCancel()

    def messageWatcher(self):
        """
        Watches for the message to be hidden after a timeout.
        """
        while True:
            time.sleep(0.1)

            if not self.message_shown:
                break

            # Measure how long it has been since the latest showMessage() call.
            # Every new message updates self.message_time, so this is a rolling
            # timeout.
            elapsed = self.timeTicksDiff(self.timeTicksMs(), self.message_time)

            # The latest message has not been visible long enough yet.
            # Keep waiting.
            if elapsed < self.message_timeout * 1000:
                continue

            # We appear to be timed out, so take control of the display bus
            # before switching screens. This prevents another display update
            # from writing halfway through the screen switch.
            self.no.busBusySet(1)

            # Re-check the elapsed time after acquiring the bus.
            # A new showMessage() call may have happened between the earlier
            # timeout check and this point, refreshing self.message_time.
            elapsed = self.timeTicksDiff(self.timeTicksMs(), self.message_time)

            # If a newer message refreshed the timeout while we were taking
            # the bus, release the bus and keep watching instead of exiting.
            if elapsed < self.message_timeout * 1000:
                self.no.busBusyCancel()
                continue

            # Only switch if the message screen is currently displayed.
            # Otherwise, this would accidentally toggle away from the main screen.
            if self.message_shown and self.no.vfd_current_screen == 2:
                self.no.switchScreenScroll(1, 0)

            # Mark message mode as finished.
            self.message_shown = False

            # Release the display bus for normal screen updates.
            self.no.busBusyCancel()
            break

        # Allow a future showMessage() call to start a fresh watcher thread.
        self.message_watcher_running = False

    def formatTone(self, percent):
        """
        Formats the tone value into a display-ready string.

        Scales the input percentage to a range from -50 to +50 and formats it 
        with explicit signs for positive and negative values.

        :param percent: The tone/balance value to format.

        :return: The formatted string with a sign (e.g. -40, 0, +17).
        """
        # Scale from percentage to the range of -50 to +50.
        value = int(percent - 50)

        # Assign clean '0' for zero, otherwise format with an explicit sign.
        if value == 0:
            return '0'
        else:
            return f'{value:+g}'

    def formatBalance(self, percent):
        """
        Formats the balance value into a display-ready string.

        Scales the input percentage to a range from -50 to +50 and formats it
        with explicit signs 'L +'/'R +' for left and right.

        :param percent: The tone/balance value to format.

        :return: The formatted string with a sign (e.g. 'R +17').
        """
        # Scale from percentage to the range of -50 to +50.
        value = int(percent - 50)

        # Assign clean '0' for zero, otherwise format with an L/R sign.
        if value == 0:
            return '0'
        elif value < 0:
            return f'L +{abs(value)}'
        else:
            return f'R +{abs(value)}'

    # .-----------------------------------------------------.
    # |                  HELPER FUNCTIONS                   |
    # '-----------------------------------------------------'

    def padText(self, new_text, old_text, prepend = False):
        """
        Pads new_text with spaces, so it's not shorter than the previous text.

        This is used for creating new text string that will be printed on
        the VFD display at a position where the old text was, which
        might have been longer. The new text to "erase" the old text needs
        to be at least as long as the old text.

        :param new_text: The text to be padded.
        :param old_text: The text to use for calculating the number of spaces.
        :param prepend: Pass True to prepend spaces in front of the new text
            instead of appending them at the end.

        :return: The new text with added padding spaces.
        """
        # Calculate the number of spaces to add.
        spaces_count = max(0, len(old_text) - len(new_text))
        spaces = spaces_count * ' '

        # Create the final text by adding spaces.
        if prepend:
            return spaces + new_text
        else:
            return new_text + spaces

    # .-----------------------------------------------------.
    # |               COMPATIBILITY FUNCTIONS               |
    # '-----------------------------------------------------'

    def timeTicksMs(self):
        """
        Cross-platform time.ticks_ms() function replacement.

        This works on MicroPython and CPython.

        :return: The current tick counter value in milliseconds.
        """
        if not self.ticks_ms:
            if hasattr(time, 'ticks_ms'):
                # MicroPython: native millisecond tick counter.
                self.ticks_ms = time.ticks_ms

            elif hasattr(time, 'monotonic_ns'):
                # CPython: high-resolution monotonic clock converted to milliseconds.
                self.ticks_ms = lambda: time.monotonic_ns() // 1000000

            elif hasattr(time, 'monotonic'):
                # Fallback: monotonic seconds converted to milliseconds.
                self.ticks_ms = lambda: int(time.monotonic() * 1000)

            else:
                raise SystemExit('timeTickMs() error: neither ticks_ms(), monotonic_ns() nor monotonic() methods exist in time.')

        return self.ticks_ms()

    def timeTicksDiff(self, ticks1, ticks2):
        """
        Cross-platform time.ticks_diff() function replacement.

        This works on MicroPython and CPython.

        :param ticks1: Newer tick value.
        :param ticks2: Older tick value.

        :return: The signed difference between the two tick values.
        """
        if not self.ticks_diff:
            if hasattr(time, 'ticks_diff'):
                # MicroPython: native tick difference, handles tick counter wraparound.
                self.ticks_diff = time.ticks_diff

            else:
                # CPython or fallback: monotonic counter does not wrap in normal use.
                self.ticks_diff = lambda arg_1, arg_2: arg_1 - arg_2

        return self.ticks_diff(ticks1, ticks2)

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
