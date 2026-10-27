import time
import network
from machine import Pin
import dht

# Dots on the start are required for RPi Pico/MicroPython boards.
from .fetchers import Fetchers
from .large_digits_3_rows import LargeDigits3Rows
from .large_digits_2_rows import LargeDigits2Rows

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

        # Large digits 3 rows, used by layout 1.
        self.digits3 = LargeDigits3Rows(self.vfd)
        # Large digits 2 rows, used by layout 2.
        self.digits2 = LargeDigits2Rows(self.vfd)

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
            self.led.value(1)
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
        self.displayed_wifi = None
        self.displayed_download = None
        self.displayed_fail = None

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
        # Button last pressed time.
        self.button_press_time = None
        # Night wake timer used when turning the display on for a moment
        # during the night.
        self.night_wake_started = None

        # Track download icon.
        self.download_icon_shown = False
        self.download_icon_time = 0

        # There are two different layouts used to show the date.
        self.layout = 2

    # .-----------------------------------------------------.
    # |                  GENERAL FUNCTIONS                  |
    # '-----------------------------------------------------'

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

    def getWeatherConditionDetails(self, conditions):
        """
        Returns the name and icon for a provided weather condition.

        :param conditions: Named weather condition.

        :return: A dictionary with the name and icon of the weather condition.
        """
        sets = {
            'Clouds': {
                'name': 'Cloud',
                'icon': 'circle_fill',
            },
            'Rain': {
                'name': 'Rain',
                'icon': 'rain',
            },
            'Thunderstorm': {
                'name': 'Storm',
                'icon': 'storm',
            },
            'Snow': {
                'name': 'Snow',
                'icon': 'snowflake',
            },
            'Sunny': {
                'name': 'Clear',
                'icon': 'circle_stroke',
            }
        }

        if conditions in sets:
            return sets[conditions]
        else:
            return sets['Sunny']
    
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

    def getNightWake(self):
        """
        Calculates if the night wake is active.

        :return bool: True if the night wake is active, False otherwise.
        """
        return (
            self.night_wake_started is not None
            and time.ticks_diff(time.ticks_ms(), self.night_wake_started) < 10_000
        )

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

    # .-----------------------------------------------------.
    # |                  BUTTON FUNCTIONS                   |
    # '-----------------------------------------------------'

    def buttonChangeBrightness(self):
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

    def buttonChangeLayout(self):
        """
        Changes the display layout used to show all the details.
        """
        # Force all elements to redraw in their new positions.
        self.displayed_time = None
        self.displayed_temperature = None
        self.displayed_humidity = None
        self.displayed_wind = None
        self.displayed_conditions = None
        self.displayed_indoor_temperature = None
        self.displayed_indoor_humidity = None
        self.displayed_wifi = None
        self.displayed_download = None
        self.displayed_fail = None

        self.last_time = None
        self.last_weather = None
        self.last_indoor = None

        self.download_icon_shown = False

        if self.layout == 1:
            self.layout = 2
            self.initScreenLayout2()
        else:
            self.layout = 1
            self.initScreenLayout1()

    def buttonDetectPress(self, dim_hours, off_hours):
        """
        Detects a button press and changes the brightness, layout, or wakes.

        Short press changes brightness during daytime and wakes the
        display during off hours.

        Long press changes the layout during daytime, dim hours,
        or an active night wake.

        :param dim_hours: Whether dim hours are active.
        :param off_hours: Whether off hours are active.
        """
        if self.button is None:
            return

        ticks_ms = time.ticks_ms()

        # Record when the button is first pressed.
        # Actions are triggered only after the button is released.
        if self.button.value() == 0:
            if self.button_press_time is None:
                self.button_press_time = ticks_ms

        # React to button release.
        elif self.button_press_time is not None:
            held_ms = time.ticks_diff(ticks_ms, self.button_press_time)

            # Reset the press time on every release, including brief presses.
            self.button_press_time = None

            # Ignore presses shorter than 100 milliseconds.
            if held_ms < 100:
                return

             # Long press changes the layout only while the display is lit.
            if held_ms >= 1500:
                if not off_hours or self.getNightWake():
                    self.buttonChangeLayout()

            # Short press wakes the display or changes daytime brightness.
            else:
                # Wake the display or restart the active night wake timer.
                if off_hours:
                    self.night_wake_started = ticks_ms

                # Change brightness only outside dim hours and off hours.
                elif not dim_hours:
                    self.buttonChangeBrightness()

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

        # Print the date and time for the current layout.
        if self.layout == 1:
            self.printDateTimeLayout1(date)
        else:
            self.printDateTimeLayout2(date)

    def printDateTimeLayout1(self, date):
        """
        Prints the date and time in layout 1.

        :param date: The date and time to print.
        """
        # Print the time if it is set.
        if date['year'] != 0:
            hour = date['hour']
            minute = date['minute']
            second = date['second']
            timestamp = date['timestamp']

            time_formatted = '{hour}:{minute}:{second}'.format(
                hour = hour,
                minute = minute,
                second = second
            )

            # Do so only if it has changed since the last print.
            if self.displayed_time != time_formatted:
                self.digits3.largeDigit(hour[0], 9)
                self.digits3.largeDigit(hour[1], 12)
                self.digits3.largeDigit(minute[0], 15)
                self.digits3.largeDigit(minute[1], 18)
                self.vfd.setCursor(17, 3)
                self.vfd.write(":{0}".format(second))

                self.displayed_time = time_formatted

                # Blinking colon between hours and minutes.
                if timestamp % 2 == 0:
                    self.digits3.largeDigit('colon', 14)
                else:
                    self.digits3.largeDigit('erase_colon', 14)

        # If time is not set, then print dashes and static colon.
        else:
            if self.displayed_time != '-':
                self.digits3.largeDigit('dash', 9)
                self.digits3.largeDigit('dash', 12)
                self.digits3.largeDigit('dash', 15)
                self.digits3.largeDigit('dash', 18)
                self.vfd.setCursor(17, 3)
                self.vfd.write(':--')

                self.displayed_time = '-'

                # Static colon when time is not known.
                self.digits3.largeDigit('colon', 14)

    def printDateTimeLayout2(self, date):
        """
        Prints the date and time in layout 2.

        :param date: The date and time to print.
        """
        # Print the time if it is set.
        if date['year'] != 0:
            hour = date['hour']
            minute = date['minute']
            second = date['second']
            timestamp = date['timestamp']

            time_formatted = '{hour}:{minute}:{second}'.format(
                hour = hour,
                minute = minute,
                second = second
            )

            # Do so only if it has changed since the last print.
            if self.displayed_time != time_formatted:
                self.digits2.largeDigit(hour[0], 7)
                self.digits2.largeDigit(hour[1], 10)
                self.digits2.largeDigit(minute[0], 14)
                self.digits2.largeDigit(minute[1], 17)
                self.vfd.setCursor(3, 3)
                self.vfd.write(":{0}".format(second))

                self.displayed_time = time_formatted

                # Blinking colon between hours and minutes.
                if timestamp % 2 == 0:
                    self.digits2.largeDigit('colon', 13)
                else:
                    self.digits2.largeDigit('erase_colon', 13)

        # If time is not set, then print dashes and static colon.
        else:
            if self.displayed_time != '-':
                self.digits2.largeDigit('dash', 7)
                self.digits2.largeDigit('dash', 10)
                self.digits2.largeDigit('dash', 14)
                self.digits2.largeDigit('dash', 17)
                self.vfd.setCursor(3, 3)
                self.vfd.write(':--')

                self.displayed_time = '-'

                # Static colon when time is not known.
                self.digits2.largeDigit('colon', 13)

    def printWeather(self):
        """
        Prints the current weather on the display.
        """
        current_ticks = time.ticks_ms()

        # Don't print weather more often than 30 seconds.
        if self.last_weather is not None and time.ticks_diff(current_ticks, self.last_weather) < 30 * 1000:
            return

        self.last_weather = current_ticks

        # Get weather data.
        weather = self.fetchers.getWeather()

        # Prepare weather data to print.
        if weather['success']:
            # Temperature should always include 1 fraction digit and occupy
            # 5 characters because it can, for example, be '-15.5'.
            temperature = '{:>5.1f}'.format(weather['temperature'])

            # Humidity should be rounded and always in range of 0-99,
            # and also always 2 characters. It should never be more
            # than 99% because of available space.
            humidity = '{:>2.0f}'.format(
                min(99, max(0, weather['humidity']))
            )

            # Wind speed should always include 1 fraction digit and occupy
            # 4 characters because it can, for example, be '15.5'.
            wind = '{:>4.1f}'.format(weather['wind'])

            conditions = weather['conditions']
        else:
            temperature = ' --.-'
            humidity = '--'
            wind = '--.-'
            conditions = None

        # Choose positions for the active layout.
        if self.layout == 1:
            temperature_pos = (2, 1)
            humidity_pos = (13, 3)
            wind_pos = (3, 2)
            conditions_pos = (2, 3)
        else:
            temperature_pos = (1, 1)
            humidity_pos = (11, 3)
            wind_pos = (2, 2)
            conditions_pos = (15, 3)

        # Print weather data.
        if self.displayed_temperature != temperature:
            self.vfd.setCursor(*temperature_pos)
            self.vfd.write(temperature)
            self.displayed_temperature = temperature

        if self.displayed_humidity != humidity:
            self.vfd.setCursor(*humidity_pos)
            self.vfd.write(humidity)
            self.displayed_humidity = humidity

        if self.displayed_wind != wind:
            self.vfd.setCursor(*wind_pos)
            self.vfd.write(wind)
            self.displayed_wind = wind

        if self.displayed_conditions != conditions:
            self.vfd.setCursor(*conditions_pos)

            if conditions is not None:
                cond = self.getWeatherConditionDetails(conditions)
                if self.layout == 1:
                    self.vfd.writeNamedChar(cond['icon'])
                else:
                    self.vfd.write('{:>5}'.format(cond['name']))
            else:
                if self.layout == 1:
                    self.vfd.write('-')
                else:
                    self.vfd.write('   --')

            self.displayed_conditions = conditions

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

        temperature = '--.-'
        humidity = '--'

        if self.sensor:
            try:
                self.sensor.measure()

                # Temperature should always include 1 fraction digit and occupy
                # 5 characters because it can, for example, be '-15.5'.
                temperature = '{:>5.1f}'.format(self.sensor.temperature())

                # Humidity should be rounded and always in range of 0-99,
                # and also always 2 characters. It should never be more
                # than 99% because of available space.
                humidity = '{:>2.0f}'.format(
                    min(99, max(0, self.sensor.humidity()))
                )

            # If the DHT22 sensor cannot be read, then displayed values will
            # be reset. If so, most probably the sensor is not connected.
            except Exception as e:
                print(f"Error reading DHT22 sensor data: {e}")

        # Choose positions for the active layout.
        if self.layout == 1:
            temperature_pos = (2, 0)
            humidity_pos = (9, 3)
        else:
            temperature_pos = (1, 0)
            humidity_pos = (7, 3)

        if self.displayed_indoor_temperature != temperature:
            self.vfd.setCursor(*temperature_pos)
            self.vfd.write(temperature)
            self.displayed_indoor_temperature = temperature

        if self.displayed_indoor_humidity != humidity:
            self.vfd.setCursor(*humidity_pos)
            self.vfd.write(humidity)
            self.displayed_indoor_humidity = humidity

    def printDownloadIcon(self):
        """
        Prints a download icon for a moment after successful data fetching.

        This icon appears each time after new data is fetched. It is used to indicate that Internet data fetching is working.

        This function also takes care of printing another icon if the last
        date and time data fetching failed.
        """
        ticks_ms = time.ticks_ms()

        # Choose position for the active layout.
        if self.layout == 1:
            pos = (4, 3)
        else:
            pos = (2, 3)

        # Show the fail icon if the last date and time fetching failed.
        if self.fetchers.date_last_failed and self.displayed_fail != 1:
            self.vfd.setCursor(*pos)
            self.vfd.write('X')
            self.displayed_fail = 1

        # Clear the fail icon (only in layout 1).
        elif not self.fetchers.date_last_failed and self.displayed_fail != 0:
            self.vfd.setCursor(*pos)
            self.vfd.write(' ')
            self.displayed_fail = 0

        # Show the download icon after successful data fetch.
        if self.fetchers.data_fetched and not self.download_icon_shown and self.displayed_fail == 0:
                self.vfd.setCursor(*pos)
                self.vfd.writeNamedChar('arrow_right')
                self.download_icon_shown = True
                self.download_icon_time = ticks_ms

        # Hide the download icon if shown and 60 seconds have passed.
        elif self.download_icon_shown and time.ticks_diff(ticks_ms, self.download_icon_time) >= (1000 * 60):
            # For layout 2 do this only if there is no fail icon.
            if self.layout == 1 or (self.layout == 2 and self.displayed_fail == 0):
                self.vfd.setCursor(*pos)
                self.vfd.write(' ')
                self.download_icon_shown = False
                self.fetchers.data_fetched = False

    def printWifiIcon(self):
        # Choose position for the active layout.
        if self.layout == 1:
            position = (0, 3)
        else:
            position = (0, 3)

        # Print the Wi-Fi icon.
        self.vfd.setCursor(*position)

        if self.wlan.isconnected() and self.displayed_wifi != 1:
            self.vfd.writeNamedChar('graph')
            self.displayed_wifi = 1

        if not self.wlan.isconnected() and self.displayed_wifi != 0:
            self.vfd.writeNamedChar('not_equal')
            self.displayed_wifi = 0

    # .-----------------------------------------------------.
    # |                    LAYOUT INITS                     |
    # '-----------------------------------------------------'

    def initScreenLayout1(self):
        """
        Initializes the display for layout 1 and prints data placeholders.
        """
        # Initialize the display.
        self.vfd.clearDisplay()

        # Initialize the large digits.
        self.digits3.largeDigitsInit()

        # Temperatures placeholders.
        self.vfd.setCursor(0, 0)
        self.vfd.write('In --.-')
        self.vfd.writeNamedChar('deg_c')

        self.vfd.setCursor(0, 1)
        self.vfd.write('Ou --.-')
        self.vfd.writeNamedChar('deg_c')

        # Wind placeholder.
        self.vfd.setCursor(0, 2)
        self.vfd.write('Wi --.-m')

        # Humidity placeholder
        self.vfd.setCursor(9, 3)
        self.vfd.write('--% --%')

        # Status icons initial.
        self.vfd.setCursor(0, 3)
        self.vfd.writeNamedChar('not_equal')

        self.vfd.setCursor(2, 3)
        self.vfd.write('-')

        # Clock placeholder.
        self.digits3.largeDigit('dash', 9)
        self.digits3.largeDigit('dash', 12)
        self.digits3.largeDigit('colon', 14)
        self.digits3.largeDigit('dash', 15)
        self.digits3.largeDigit('dash', 18)
        self.vfd.setCursor(17, 3)
        self.vfd.write(':--')

    def initScreenLayout2(self):
        """
        Initializes the display for layout 2 and prints data placeholders.
        """
        # Initialize the display.
        self.vfd.clearDisplay()

        # Initialize the large digits.
        self.digits2.largeDigitsInit()

        # Temperatures placeholders.
        self.vfd.setCursor(0, 0)
        self.vfd.write('i --.-')

        self.vfd.setCursor(0, 1)
        self.vfd.write('o --.-')

        # Wind placeholder.
        self.vfd.setCursor(0, 2)
        self.vfd.write('w --.-')

        # Humidity placeholder
        self.vfd.setCursor(7, 3)
        self.vfd.write('--% --%')

        # Conditions.
        self.vfd.setCursor(15, 3)
        self.vfd.write('   --')

        # Status icons initial.
        self.vfd.setCursor(0, 3)
        self.vfd.writeNamedChar('not_equal')

        # Clock placeholder.
        self.digits2.largeDigit('dash', 7)
        self.digits2.largeDigit('dash', 10)
        self.digits2.largeDigit('colon', 13)
        self.digits2.largeDigit('dash', 14)
        self.digits2.largeDigit('dash', 17)
        self.vfd.setCursor(3, 3)
        self.vfd.write(':--')

    # .-----------------------------------------------------.
    # |                      MAIN LOOP                      |
    # '-----------------------------------------------------'

    def keepRunning(self):
        """
        The main loop that keeps the info display running.
        """
        # Initialize the first screen layout.
        if self.layout == 1:
            self.initScreenLayout1()
        else:
            self.initScreenLayout2()

        # Connect to Wi-Fi.
        self.connectWifi()

        # If Wi-Fi has connected, show W-Fi connection icon.
        self.printWifiIcon()

        while True:
            # Update displayed time (fetches new every 2 hours).
            self.printDateTime()

            # Update displayed weather (fetches new every 10 minutes).
            self.printWeather()

            # Update indoor temperature and humidity.
            self.printIndoorTemp()

            # Update download icon.
            self.printDownloadIcon()

            # Check if dim hours and off hours are active.
            dim_off = self.getDimOff()
            off_hours = dim_off['off_hours']
            dim_hours = dim_off['dim_hours']

            # Detect button press.
            self.buttonDetectPress(dim_hours, off_hours)

            # Get current night wake status.
            # This needs to happen after the button press detection.
            night_wake = self.getNightWake()

            # Update night/day brightness.
            self.setNightDayBrightness(dim_hours, off_hours, night_wake)

            # Reconnect Wi-Fi if needed.
            if not self.wlan.isconnected():
                # Indicate no Wi-Fi connection by setting the connection icon
                # before trying to reconnect.
                self.printWifiIcon()
                # Reconnect.
                self.connectWifi()

            # If Wi-Fi has connected, show an icon.
            self.printWifiIcon()

            # Wait.
            time.sleep(0.1)
