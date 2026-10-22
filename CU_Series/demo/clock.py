import time
import network
import requests
from machine import RTC

# Dots on the start are required for RPi Pico/MicroPython boards.
from .fetchers import Fetchers
from .large_digits_2_rows import LargeDigits
from .matrix_rain import MatrixRain

# Import config_local.py if user has created it.
try:
    from . import config_local as config
# Otherwise import config.py (assuming the user has customized it).
except ImportError:
    from . import config as config

class ClockTemp:
    """
    Displays a local time clock and local weather data.
    """

    def __init__(self, vfd, lines, cols):
        # Display details.
        self.vfd = vfd
        self.lines = lines
        self.cols = cols

        # Data fetchers, for fetching weather and time from the Internet.
        self.fetchers = Fetchers()

        # Large digits.
        self.digits = LargeDigits(self.vfd)

        # Wi-Fi.
        self.wlan = network.WLAN(network.STA_IF)
        self.ssid = config.wifi_ssid
        self.password = config.wifi_password
        self.wifi_last_attempt = None
        self.wifi_retry_interval = 10 * 1000

        # Track last displayed values.
        # This prevents writing data that did not change to the display.
        self.displayed_time = None
        self.displayed_temperature = None
        self.displayed_humidity = None

        # Track the last time when values were displayed.
        # This is used to prevent calling print methods more
        # often than necessary.
        self.last_time = None
        self.last_weather = None

        # Track brightness.
        # Current brightness status (on, dimed, off).
        self.brightness_status = 'on'

        # Matrix Rain animation shown at every full hour.
        self.matrix = MatrixRain(self.vfd, lines, cols)
        self.matrix_last_hour = None

    def connectWifi(self):
        """
        Connects to the Wi-Fi network, retries if the SSID is unavailable.
        """
        # TODO: Improve the Wi-Fi connecting so it is non-blocking.
        current_ticks = time.ticks_ms()

        # Do not retry connecting more often than the configured interval.
        if (
            self.wifi_last_attempt is not None and
            time.ticks_diff(current_ticks, self.wifi_last_attempt)
            < self.wifi_retry_interval
        ):
            return False

        self.wifi_last_attempt = current_ticks
        self.wlan.active(True)

        # Indicate that connection is in progress.
        self.vfd.clearDisplay()
        self.vfd.setCursor(0, 0)
        self.vfd.write('Connecting Wi-Fi')
        print('Trying to connect to Wi-Fi...')

        try:
            # Initiate a connection and give it up to 10 seconds.
            try:
                self.wlan.connect(self.ssid, self.password)
                for _ in range(10):
                    if self.wlan.isconnected():
                        break
                    time.sleep(1)
            except OSError as e:
                print('Wi-Fi connection error:', e)
                try:
                    self.wlan.disconnect()
                except OSError:
                    pass
                return False

            if not self.wlan.isconnected():
                try:
                    self.wlan.disconnect()
                except OSError:
                    pass
                print('Wi-Fi unavailable; retrying...')
                return False

            # Indicate that connection was successful.
            self.vfd.clearDisplay()
            self.vfd.setCursor(0, 0)
            self.vfd.write('Wi-Fi connected')
            print('Established Wi-Fi connection.')

            time.sleep(1.5)
            return True

        finally:
            # Wait the retry interval after this attempt finishes.
            self.wifi_last_attempt = time.ticks_ms()

            # Restore the clock and weather after every connection attempt.
            self.vfd.clearDisplay()
            self.displayed_time = None
            self.displayed_temperature = None
            self.displayed_humidity = None
            self.last_time = None
            self.last_weather = None

    def checkHourInRange(self, hour, start, end):
        """
        Checks if the given hour is in the given range.

        :param hour: The hours to check, e.g., 3 or 22.
        :param start: The start hour of the range.
        :param end: The end hour of the range.

        :return: True if the hour is in the range, False otherwise.
        """
        if start == end:
            return False

        if start < end:
            return start <= hour < end

        return hour >= start or hour < end

    def printDateTime(self):
        """
        Prints the current time on the display.
        """
        current_ticks = time.ticks_ms()

        # Don't print time more often than every 0.2 seconds.
        if self.last_time is not None and time.ticks_diff(current_ticks, self.last_time) < 200:
            return

        self.last_time = current_ticks

        # Get date and time.
        date = self.fetchers.getDateTime()

        # Print the time if it is set.
        if date['year'] != 0:
            time_formatted = '{hour}:{minute}:{second}'.format(
                hour = date['hour'],
                minute = date['minute'],
                second = date['second']
            )

            # Do so only if it has changed since the last print.
            if self.displayed_time != time_formatted:
                hour = str(date['hour'])
                minute = str(date['minute'])

                self.digits.largeDigit(hour[0], 0)
                self.digits.largeDigit(hour[1], 3)
                self.digits.largeDigit(minute[0], 7)
                self.digits.largeDigit(minute[1], 10)

                self.displayed_time = time_formatted

                # Blinking colon between hours and minutes.
                if (date['timestamp'] % 2) == 0:
                    self.digits.largeDigit('colon', 6)
                else:
                    self.digits.largeDigit('erase_colon', 6)

        # If time is not set, then print dashes and static colon.
        else:
            if self.displayed_time != '-':
                self.digits.largeDigit('dash', 0)
                self.digits.largeDigit('dash', 3)
                self.digits.largeDigit('dash', 7)
                self.digits.largeDigit('dash', 10)
                self.digits.largeDigit('colon', 6)
                self.displayed_time = '-'

    def printWeather(self):
        """
        Prints current weather on the display.
        """
        current_ticks = time.ticks_ms()

        # Don't print weather more often than 30 seconds.
        if (
            self.displayed_temperature is not None
            and self.displayed_humidity is not None
            and self.last_weather is not None
            and time.ticks_diff(current_ticks, self.last_weather) < 30 * 1000
        ):
            return

        self.last_weather = current_ticks

        # Get weather data.
        weather = self.fetchers.getWeather()

        # Print weather if it was fetched.
        if weather['success']:
            temperature = weather['temperature']
            humidity = weather['humidity']

            # Temperature should be rounded and always occupying 3
            # characters because it can, for example, be 5 or -12.
            temperature = '{:>3.0f}'.format(temperature)

            # Humidity should be rounded and always in range of 0-99,
            # and also always 2 characters. It should never be more
            # than 99% because of available space.
            if humidity > 99:
                humidity = 99

            # Humidity should always be 2 characters.
            humidity = '{:>2.0f}'.format(humidity)

            if self.displayed_temperature != temperature:
                self.vfd.setCursor(13, 0)
                self.vfd.writeText(temperature)
                self.displayed_temperature = temperature

            if self.displayed_humidity != humidity:
                self.vfd.setCursor(14, 1)
                self.vfd.writeText(humidity)
                self.displayed_humidity = humidity

        # Clear weather when the fetching has failed.
        else:
            if self.displayed_temperature != '--':
                self.vfd.setCursor(13, 0)
                self.vfd.writeText(' --')
                self.displayed_temperature = '--'

                self.vfd.setCursor(14, 1)
                self.vfd.writeText('--')
                self.displayed_humidity = '--'

    def screenInit(self):
        """
        Initializes VFD large digits and prints a message and then placeholders.
        """
        # Initialize the display.
        self.vfd.clearDisplay()

        # Initialize the large digits.
        self.digits.largeDigitsInit()

        # Show fetching data message.
        self.vfd.clearDisplay()
        self.vfd.setCursor(0, 0)
        self.vfd.write('Fetching data')
        time.sleep(2)

        # Show time placeholders.
        self.vfd.clearDisplay()
        self.digits.largeDigit('dash', 0)
        self.digits.largeDigit('dash', 3)
        self.digits.largeDigit('dash', 7)
        self.digits.largeDigit('dash', 10)
        self.digits.largeDigit('colon', 6)

        # Show weather placeholders.
        self.vfd.setCursor(14, 0)
        self.vfd.writeText('--')
        self.vfd.setCursor(14, 1)
        self.vfd.writeText('--')

    def keepRunning(self):
        """
        The main loop that keeps the clock running.
        """
        self.connectWifi()
        self.screenInit()

        while True:
            # Update displayed time (fetches new every 2 hours).
            self.printDateTime()

            # Update displayed weather (fetches new every 10 minutes).
            self.printWeather()

            # Time needed for further operations.
            date = self.fetchers.getDateTime()

            # Screen dimming at night (requires parallel connection).
            if date['year'] != 0:
                hour = date['hour_int']

                off_hours = self.checkHourInRange(
                    hour,
                    config.display_off_start_hour,
                    config.display_off_end_hour
                )

                dim_hours = self.checkHourInRange(
                    hour,
                    config.display_dim_start_hour,
                    config.display_dim_end_hour
                )

                # Off hours.
                if off_hours:
                    if self.brightness_status != 'off':
                        self.vfd.displayOnOff(0)
                        self.brightness_status = 'off'

                # Dim hours.
                elif dim_hours:
                    if self.brightness_status != 'dim':
                        self.vfd.displayOnOff(1)
                        self.vfd.setBrightness(1)
                        self.brightness_status = 'dim'

                # On hours.
                elif self.brightness_status != 'on':
                    self.vfd.displayOnOff(1)
                    self.vfd.setBrightness(4)
                    self.brightness_status = 'on'

            # Show Matrix Rain animation once in an hour, e.g., at 5:00 or 12:00.
            if date['year'] != 0 and config.matrix_rain_duration != 0:
                hour = date['hour_int']
                minute = date['minute_int']

                if self.matrix_last_hour != hour and minute == 0:
                    self.matrix_last_hour = hour

                    self.matrix.animate(config.matrix_rain_duration)
                    self.vfd.clearDisplay()

                    # Reset displayed clock data so that it is rewritten.
                    self.displayed_time = None
                    self.displayed_temperature = None
                    self.displayed_humidity = None
                    self.last_weather = None
                    self.last_time = None

            # Reconnect Wi-Fi if needed.
            if not self.wlan.isconnected():
                self.connectWifi()

            time.sleep(0.1)
