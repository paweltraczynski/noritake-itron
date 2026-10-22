import time
import network
from machine import Pin
import dht

# Dots on the start are required for RPi Pico/MicroPython boards.
from .fetchers import Fetchers
from .large_digits_3_rows import LargeDigits

# Import config_local.py if user has created it.
try:
    from . import config_local as config
# Otherwise import config.py (assuming the user has customized it).
except ImportError:
    from . import config

class WeatherClock:
    """
    Displays a local time clock, local weather, and indoor temperature.

    This is written for MicroPython.

    :param vfd: The Noritake CU class (GPIO or I2C).
    :param lines: The number of lines on the display.
    :param cols: The number of columns on the display.
    :param dht_pin: The number of the DHT22 sensor pin.
      Leave blank if you have not connected the sensor.
    :param button_pin: The number of the button pin.
      Leave blank if you have not connected the button.
    :param led_pin: The number of the LED pin.
      Leave blank if you have not connected the LED.
    """

    def __init__(self, vfd, lines, cols, dht_pin = None, button_pin = None, led_pin = None):
        # Display details.
        self.vfd = vfd
        self.lines = lines
        self.cols = cols

        # Data fetchers, for fetching weather and time from the Internet.
        self.fetchers = Fetchers()

        # Large digits.
        self.digits = LargeDigits(self.vfd)

        # DHT22 sensor.
        if dht_pin is not None:
            self.sensor = dht.DHT22(Pin(dht_pin))
        else:
            self.sensor = None

        # Button for changing the brightness.
        if button_pin is not None:
            self.button = Pin(button_pin, Pin.IN, Pin.PULL_UP)
        else:
            self.button = None

        # LED.
        if led_pin is not None:
            self.led = Pin(led_pin, Pin.OUT)
        else:
            self.led = None

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
        self.displayed_wind = None
        self.displayed_conditions = None
        self.displayed_indoor_temperature = None
        self.displayed_indoor_humidity = None

        # Track the last time when values were displayed.
        # This is used to prevent calling print methods more
        # often than necessary.
        self.last_time = None
        self.last_weather = None
        self.last_indoor = None

        # Track brightness.
        # Current brightness status (on, dimed, off).
        self.brightness_status = 'on'
        # Last user set brightness.
        self.brightness_set = 4
        # Brightness changing button last pressed time.
        self.brightness_button = None
        # Night wake timer used when turning the display on for a moment
        # during the night.
        self.night_wake_started = None

        # Track download icon.
        self.download_icon_shown = False
        self.download_icon_time = 0

    def connectWifi(self):
        """
        Connects to the Wi-Fi network, retries if the SSID is unavailable.
        """
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

        # Indicate no Wi-Fi connection by settings the connection icon.
        self.vfd.setCursor(0, 3)
        self.vfd.writeNamedChar('not_equal')

        # Initiate a Wi-Fi connection.
        try:
            self.wlan.connect(self.ssid, self.password)
        except OSError:
            return False

        # Give this attempt up to 10 seconds.
        for _ in range(10):
            if self.wlan.isconnected():
                break
            time.sleep(1)

        # Because up to 10 seconds might have passed, update the last attempt.
        self.wifi_last_attempt = time.ticks_ms()

        # If the connection failed, then try to disconnect before retrying.
        if not self.wlan.isconnected():
            try:
                self.wlan.disconnect()
            except OSError:
                pass

            print('Wi-Fi unavailable; retrying...')
            return False

        # At this point, the connection has been established.
        self.vfd.setCursor(0, 3)
        self.vfd.writeNamedChar('graph')

        print('Established Wi-Fi connection.')
        return True

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

    def changeBrightness(self):
        """
        Continuously changes the brightness by 1 brightness level.
        """
        # Each time the brightness gets decreased by 1.
        brightness = self.brightness_set - 1

        # After reaching the minimum brightness, reset to maximum.
        if brightness < 1:
            brightness = 4

        self.brightness_set = brightness

        if self.brightness_status == 'on':
            self.vfd.setBrightness(brightness)

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

                self.digits.largeDigit(hour[0], 9)
                self.digits.largeDigit(hour[1], 12)
                self.digits.largeDigit(minute[0], 15)
                self.digits.largeDigit(minute[1], 18)
                self.vfd.setCursor(17, 3)
                self.vfd.write(":{0}".format(date['second']))

                self.displayed_time = time_formatted

                # Blinking colon between hours and minutes.
                if date['timestamp'] % 2 == 0:
                    self.digits.largeDigit('colon', 14)
                else:
                    self.digits.largeDigit('erase_colon', 14)

        # If time is not set, then print dashes and static colon.
        else:
            if self.displayed_time != '-':
                self.digits.largeDigit('dash', 9)
                self.digits.largeDigit('dash', 12)
                self.digits.largeDigit('dash', 15)
                self.digits.largeDigit('dash', 18)
                self.vfd.setCursor(17, 3)
                self.vfd.write(':--')

                self.displayed_time = '-'

                # Static colon when time is not known.
                self.digits.largeDigit('colon', 14)

    def printWeather(self):
        current_ticks = time.ticks_ms()

        # Don't print weather more often than 30 seconds.
        if self.last_weather is not None and time.ticks_diff(current_ticks, self.last_weather) < 30 * 1000:
            return

        self.last_weather = current_ticks

        # Get weather data.
        weather = self.fetchers.getWeather()

        # Print weather if it was fetched.
        if weather['success']:
            temperature = weather['temperature']
            humidity = weather['humidity']
            wind = weather['wind']
            conditions = weather['conditions']

            # Temperature should always include 1 fraction digit
            # occupying 5 characters because it can, for example, be '-15.5'.
            temperature = '{:>5.1f}'.format(temperature)

            # Humidity should be rounded and always in range of 0-99,
            # and also always 2 characters. It should never be more
            # than 99% because of available space.
            if humidity > 99:
                humidity = 99
            humidity = '{:>2}'.format(humidity)

            # Wind speed should always include 1 fraction digit
            # occupying 4 characters because it can, for example, be '15.5'.
            wind = '{:>4.1f}'.format(wind)


            # Print temperature.
            if self.displayed_temperature != temperature:
                self.vfd.setCursor(2, 2)
                self.vfd.write(temperature)
                self.displayed_temperature = temperature

            # Print humidity.
            if self.displayed_humidity != humidity:
                self.vfd.setCursor(13, 3)
                self.vfd.write(humidity)
                self.displayed_humidity = humidity

            # Print wind speed.
            if self.displayed_wind != wind:
                # TODO: Set position.
                self.vfd.setCursor(2, 4)
                self.vfd.write(wind)
                self.displayed_wind = wind

            # Print icon for indicating weather conditions.
            if self.displayed_conditions != conditions:
                self.vfd.setCursor(2, 3)
                self.displayed_conditions = conditions

                # Clouds.
                if conditions == 'Clouds':
                    self.vfd.writeNamedChar('circle_fill')
                # Rain.
                elif conditions == 'Rain' or conditions == 'Thunderstorm':
                    self.vfd.writeData(0xd9)
                # Snow.
                elif conditions == 'Snow':
                    self.vfd.write('*')
                # Sunny.
                else:
                    self.vfd.writeNamedChar('circle_stroke')

        # Clear weather when the fetching has failed.
        else:
            # Print temperature.
            self.vfd.setCursor(2, 2)
            self.vfd.write(' --.-')
            self.displayed_temperature = ' --.-'

            # Print humidity.
            self.vfd.setCursor(13, 3)
            self.vfd.write('--')
            self.displayed_humidity = '--'

            # Print wind speed.
            # TODO: Set position.
            self.vfd.setCursor(2, 4)
            self.vfd.write('--')
            self.displayed_wind = '--.-'

            # Print icon for indicating weather conditions.
            self.vfd.setCursor(2, 3)
            self.vfd.write('-')
            self.displayed_conditions = '-'

    def printIndoorTemp(self):
        """
        Prints the indoor temperature and humidity.

        This function relies on the presence of the DHT22 sensor.
        """
        current_ticks = time.ticks_ms()

        # Don't print indoor temperature more often than every 30 seconds.
        if self.last_indoor is not None and time.ticks_diff(current_ticks, self.last_indoor) < 30 * 1000:
            return

        self.last_indoor = current_ticks

        if self.sensor:
            try:
                self.sensor.measure()
                temperature = round(self.sensor.temperature(), 1)
                humidity = round(self.sensor.humidity())

            # If the DHT22 sensor cannot be read, then return.
            # Most probably the sensor is not connected.
            except Exception as e:
                print(f"Error reading DHT22 sensor data: {e}")
                return

            # Indoor temperature should always include 1 fraction digit
            # occupying 4 characters because it can, for example, be '23.5'.
            temperature = '{:>4.1f}'.format(temperature)

            # Humidity should never be more than 99% because of available space.
            if humidity > 99:
                humidity = 99
            humidity = '{:>2}'.format(humidity)

            self.vfd.setCursor(3, 0)
            self.vfd.write(temperature)
            self.vfd.setCursor(9, 3)
            self.vfd.write(humidity)

    def screenInit(self):
        """
        Initializes the display, large digits and prints data placeholders.
        """
        # Initialize the display.
        self.vfd.clearDisplay()

        # Initialize the large digits.
        self.digits.largeDigitsInit()

        # Temperatures placeholders.
        self.vfd.write('In --.-')
        self.vfd.writeNamedChar('deg_c')
        self.vfd.setCursor(0, 1)
        self.vfd.write('Out')
        self.vfd.setCursor(3, 2)
        self.vfd.write('--.-')
        self.vfd.writeNamedChar('deg_c')

        # Status icons initial.
        self.vfd.setCursor(0, 3)
        self.vfd.writeNamedChar('not_equal')
        self.vfd.setCursor(2, 3)
        self.vfd.write('-')

        # Humidity placeholder
        self.vfd.setCursor(9, 3)
        self.vfd.write('--% --%')

        # Clock placeholder.
        self.digits.largeDigit('dash', 9)
        self.digits.largeDigit('dash', 12)
        self.digits.largeDigit('colon', 14)
        self.digits.largeDigit('dash', 15)
        self.digits.largeDigit('dash', 18)
        self.vfd.setCursor(17, 3)
        self.vfd.write(':--')

    def keepRunning(self):
        """
        The main loop that keeps the info display running.
        """
        self.screenInit()
        self.connectWifi()

        # Enable the LED at startup.
        if self.led is not None:
            self.led.value(1)

        while True:
            # Update displayed time (fetches new every 2 hours).
            self.printDateTime()

            # Update displayed weather (fetches new every 10 minutes).
            self.printWeather()

            # Update indoor temperature and humidity.
            self.printIndoorTemp()

            # Detect dim and off hours.
            date = self.fetchers.getDateTime()

            off_hours = False
            dim_hours = False

            if date['year'] != 0:
                off_hours = self.checkHourInRange(
                    date['hour_int'],
                    config.display_off_start_hour,
                    config.display_off_end_hour
                )

                dim_hours = self.checkHourInRange(
                    date['hour_int'],
                    config.display_dim_start_hour,
                    config.display_dim_end_hour
                )

            # Ticks after potential fetching of data from the Internet.
            ticks_ms = time.ticks_ms()

            # Update download icon.
            if self.fetchers.data_fetched and not self.download_icon_shown:
                # Show icon if not shown but flagged to start appearing.
                self.vfd.setCursor(4, 3)
                self.vfd.writeNamedChar('arrow_right')
                self.download_icon_shown = True
                self.download_icon_time = ticks_ms

            elif self.download_icon_shown and time.ticks_diff(ticks_ms, self.download_icon_time) >= (1000 * 60):
                # Hide icon if shown and 60 seconds have passed.
                self.vfd.setCursor(4, 3)
                self.vfd.write(' ')
                self.download_icon_shown = False
                self.fetchers.data_fetched = False

            # Handle brightness button.
            if self.button is not None:
                if self.button.value() == 0:
                    if self.brightness_button is None:
                        self.brightness_button = ticks_ms

                        # Button triggers night wake at night.
                        if off_hours:
                            self.night_wake_started = ticks_ms
                else:
                    if self.brightness_button is not None:
                        if time.ticks_diff(ticks_ms, self.brightness_button) >= 100:
                            if not off_hours and not dim_hours:
                                self.changeBrightness()
                            self.brightness_button = None

            # Calculate if the night wake is active.
            night_wake_active = (
                self.night_wake_started is not None
                and time.ticks_diff(ticks_ms, self.night_wake_started) < 10_000
            )

            # Update night/day brightness.
            # Off hours.
            if off_hours:
                if night_wake_active:
                    if self.brightness_status != 'night_wake':
                        self.vfd.displayOnOff(1)
                        self.vfd.setBrightness(1)
                        self.brightness_status = 'night_wake'
                        if self.led is not None:
                            self.led.value(1)
                elif self.brightness_status != 'off':
                    self.vfd.displayOnOff(0)
                    self.brightness_status = 'off'
                    if self.led is not None:
                            self.led.value(0)

            # Dim hours.
            elif dim_hours:
                if self.brightness_status != 'dim':
                    self.vfd.displayOnOff(1)
                    self.vfd.setBrightness(1)
                    self.brightness_status = 'dim'
                    if self.led is not None:
                        self.led.value(1)

            # On hours.
            elif self.brightness_status != 'on':
                self.vfd.displayOnOff(1)
                self.vfd.setBrightness(self.brightness_set)
                self.brightness_status = 'on'
                if self.led is not None:
                    self.led.value(1)

            # Reconnect Wi-Fi if needed.
            if not self.wlan.isconnected():
                self.connectWifi()

            # Wait.
            time.sleep(0.1)
