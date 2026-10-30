import time

# Use relative imports for modules in the current package.
from .wifi import WiFiConnection
from .fetchers import Fetchers
from .large_digits_2_rows import LargeDigits2Rows
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

    :param vfd: The Noritake CU class instance (GPIO or I2C).
    :param lines: The number of lines on the display.
    :param cols: The number of columns on the display.
    """

    def __init__(self, vfd, lines, cols):
        # Display details.
        self.vfd = vfd
        self.lines = lines
        self.cols = cols

        # Data fetchers, for fetching weather and time from the Internet.
        self.fetchers = Fetchers()

        # Large digits.
        self.digits = LargeDigits2Rows(self.vfd)

        # Wi-Fi.
        self.wifi = WiFiConnection(config.wifi_ssid, config.wifi_password)

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
        # Current brightness status (on, dim, off).
        self.brightness_status = 'on'

        # Matrix Rain animation shown at every full hour.
        self.matrix = MatrixRain(self.vfd, lines, cols)
        self.matrix_last_hour = None

    # .-----------------------------------------------------.
    # |                  GENERAL FUNCTIONS                  |
    # '-----------------------------------------------------'

    def connectWifi(self):
        """
        Connects to the Wi-Fi network, retries if the SSID is unavailable.
        """
        # Indicate that connection is in progress.
        self.vfd.clearDisplay()
        self.vfd.setCursor(0, 0)
        self.vfd.write('Connecting Wi-Fi')
        print('Trying to connect to Wi-Fi...')

        connected = self.wifi.connect()

        if connected:
            self.vfd.clearDisplay()
            self.vfd.setCursor(0, 0)
            self.vfd.write('Wi-Fi connected')
            time.sleep(1.5)

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

    def getDimOff(self):
        """
        Returns information if dim hours and off hours are active.

        :return: The information about dim hours and off hours.
        """
        date = self.fetchers.getDateTime()

        # Prepare the result.
        result = {
            'dim_hours': False,
            'off_hours': False,
        }

        # Calculate if dim hours or off hours are active.
        if date['year'] != 0:
            result['dim_hours'] = self.checkHourInRange(
                date['hour_int'],
                config.display_dim_start_hour,
                config.display_dim_end_hour
            )

            result['off_hours'] = self.checkHourInRange(
                date['hour_int'],
                config.display_off_start_hour,
                config.display_off_end_hour
            )

        return result

    def setNightDayBrightness(self, dim_hours, off_hours, night_wake):
        """
        Sets the brightness based on the dim/off and night wake status.

        :param dim_hours: True if dim hours are active, False otherwise.
        :param off_hours: True if off hours are active, False otherwise.
        :param night_wake: True if a night wake is active, False otherwise.
        """
        if off_hours:
            if night_wake:
                if self.brightness_status != 'night_wake':
                    self.vfd.displayOnOff(1)
                    self.vfd.setBrightness(1)
                    self.brightness_status = 'night_wake'

            elif self.brightness_status != 'off':
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

    # .-----------------------------------------------------.
    # |                 PRINTING FUNCTIONS                  |
    # '-----------------------------------------------------'

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
            # Temperature should be rounded and always occupying 3
            # characters because it can, for example, be 5 or -12.
            temperature = '{:>3.0f}'.format(
                min(999, max(-99, weather['temperature']))
            )

            # Humidity should be rounded and always in range of 0-99,
            # and also always 2 characters. It should never be more
            # than 99% because of available space.
            humidity = '{:>2.0f}'.format(
                min(99, max(0, weather['humidity']))
            )

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

    def printMatrixRain(self):
        """
        Shows Matrix Rain once in every full hour.
        """
        if config.matrix_rain_duration == 0:
            return

        date = self.fetchers.getDateTime()

        if date['year'] == 0:
            return

        hour = date['hour_int']
        minute = date['minute_int']

        if self.matrix_last_hour == hour or minute != 0:
            return

        self.matrix_last_hour = hour

        self.matrix.animate(config.matrix_rain_duration)

        # Restore the clock screen after the animation.
        self.initScreen()

        # Reset displayed clock data so that it is rewritten.
        self.displayed_time = None
        self.displayed_temperature = None
        self.displayed_humidity = None
        self.last_weather = None
        self.last_time = None

    # .-----------------------------------------------------.
    # |                    LAYOUT INITS                     |
    # '-----------------------------------------------------'

    def initScreen(self):
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

    # .-----------------------------------------------------.
    # |                      MAIN LOOP                      |
    # '-----------------------------------------------------'

    def keepRunning(self):
        """
        The main loop that keeps the clock running.
        """
        # Connect to Wi-Fi.
        self.connectWifi()

        # Initialize the screen layout.
        self.initScreen()

        while True:
            # Update displayed time (fetches new every 2 hours).
            self.printDateTime()

            # Update displayed weather (fetches new every 10 minutes).
            self.printWeather()

            # Check if dim hours and off hours are active.
            dim_off = self.getDimOff()
            off_hours = dim_off['off_hours']
            dim_hours = dim_off['dim_hours']

            # Update night/day brightness.
            night_wake = False
            self.setNightDayBrightness(dim_hours, off_hours, night_wake)

            # Show Matrix Rain animation on every full hour, e.g., at 5:00.
            self.printMatrixRain()

            # Reconnect Wi-Fi if needed.
            if not self.wifi.isConnected():
                self.connectWifi()

            # Wait.
            time.sleep(0.1)
