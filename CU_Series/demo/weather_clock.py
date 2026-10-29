import time
from machine import Pin
import dht

# Use relative imports for modules in the current package.
from .wifi import WiFiConnection
from .settings_handler import SettingsHandler
from .fetchers import Fetchers
from .large_digits_3_rows import LargeDigits3Rows
from .large_digits_2_rows import LargeDigits2Rows
from .matrix_rain import MatrixRain

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

    :param vfd: The Noritake CU class instance (GPIO or I2C).
    :param lines: The number of lines on the display.
    :param cols: The number of columns on the display.
    :param dht_pin: The number of the DHT22 sensor pin.
      Omit or pass None if you have not connected the sensor.
    :param button_pin: The number of the button pin.
      Omit or pass None if you have not connected the button.
    :param led_pin: The number of the LED pin.
      Omit or pass None if you have not connected the LED.
    """

    def __init__(self, vfd, lines, cols, dht_pin = None, button_pin = None, led_pin = None):
        # Display details.
        self.vfd = vfd
        self.lines = lines
        self.cols = cols

        # Data fetchers, for fetching weather and time from the Internet.
        self.fetchers = Fetchers()

        # Settings handler.
        self.settings_handler = SettingsHandler('settings.txt', {
            'layout': 1,
            'brightness': 4,
            'led': 4,
        })
        settings = self.settings_handler.getSettings()

        # Large digits 3 rows, used by layout 1.
        self.digits3 = LargeDigits3Rows(self.vfd)
        # Large digits 2 rows, used by layout 2.
        self.digits2 = LargeDigits2Rows(self.vfd)

        # DHT22 sensor.
        if dht_pin is not None:
            self.sensor = dht.DHT22(Pin(dht_pin))
        else:
            self.sensor = None

        self.dht_temperature_offset = config.dht_temperature_offset
        self.dht_humidity_offset = config.dht_humidity_offset

        # Button for the display/LED brightness, layout selection, and night wake.
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
        self.wifi = WiFiConnection(config.wifi_ssid, config.wifi_password)

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

        # Track when display data was last checked for changes.
        # This prevents writing to the VFD more often than necessary.
        self.last_time = None
        self.last_weather = None
        self.last_indoor = None

        # Track display brightness.
        # Current display brightness status (on, dim, off, or night_wake).
        self.brightness_status = 'on'
        # Night wake timer used when turning the display on for a moment
        # during the night.
        self.night_wake_started = None

        # Button last pressed time.
        self.button_press_time = None
        self.button_long_handled = False

        # Track download icon display time.
        self.download_icon_time = 0

        # Last user set display brightness.
        self.display_brightness = settings['brightness']
        if self.display_brightness not in (1, 2, 3, 4):
            self.display_brightness = 4

        # Last user set LED brightness (0 is off).
        self.led_brightness = settings['led']
        if self.led_brightness not in (0, 1, 2, 3, 4):
            self.led_brightness = 4

        # There are two different layouts used to show the data.
        self.layout = settings['layout']
        if self.layout not in (1, 2):
            self.layout = 1

        # Matrix Rain animation shown at every full hour.
        self.matrix = MatrixRain(self.vfd, lines, cols)
        self.matrix_last_hour = None

        # TODO: Implement saving LED in settings.txt file.

        # TODO: Implement button double click to walk through LED brightness level and turn off.

        # TODO: Implement LED PWM brightness levels.

        # TODO: Isolate DHT22 physically from internal air.

    # .-----------------------------------------------------.
    # |                  GENERAL FUNCTIONS                  |
    # '-----------------------------------------------------'

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
        Returns the display name and icon for an OpenWeatherMap condition code.

        Drizzle is displayed as rain. Mist and fog share a separate entry.
        Unrecognized conditions use a neutral placeholder.

        :param conditions: The numeric OpenWeatherMap condition code.

        :return: A dictionary containing the display name and named icon.
        """
        if conditions is None:
            return {'name': '--', 'icon': 'dash_x'}

        # Thunderstorms.
        if 200 <= conditions < 300:
            return {'name': 'Storm', 'icon': 'storm'}

        # Drizzle and rain.
        if 300 <= conditions < 400 or 500 <= conditions < 600:
            return {'name': 'Rain', 'icon': 'rain'}

        # Snow and sleet.
        if 600 <= conditions < 700:
            return {'name': 'Snow', 'icon': 'snowflake'}

        # Mist and fog.
        if conditions in (701, 741):
            return {'name': 'Fog', 'icon': 'triple_line'}

        # Clear sky.
        if conditions == 800:
            return {'name': 'Clear', 'icon': 'circle_stroke'}

        # Cloud cover.
        if 801 <= conditions <= 804:
            return {'name': 'Cloud', 'icon': 'circle_fill'}

        # Other conditions, including smoke, dust, and volcanic ash.
        return {'name': '--', 'icon': 'dash_x'}
    
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

        :return: True if the night wake is active, False otherwise.
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
            self.vfd.setBrightness(self.display_brightness)
            self.brightness_status = 'on'
            if self.led is not None:
                self.led.value(1)

    def resetDisplayedState(self):
        """
        Resets display states, which forces all display elements to be redrawn.
        """
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

    # .-----------------------------------------------------.
    # |                  BUTTON FUNCTIONS                   |
    # '-----------------------------------------------------'

    def buttonChangeBrightness(self):
        """
        Cycles through the available display brightness levels.
        """
        # Each time the brightness gets decreased by 1.
        brightness = self.display_brightness - 1

        # After reaching the minimum brightness, reset to maximum.
        if brightness < 1:
            brightness = 4

        self.display_brightness = brightness

        self.settings_handler.saveSingleSetting('brightness', brightness)
        self.vfd.setBrightness(brightness)

    def buttonChangeLayout(self):
        """
        Changes the display layout used to show all the details.
        """
        # Force all elements to redraw in their new positions.
        self.resetDisplayedState()

        if self.layout == 1:
            self.layout = 2
            self.settings_handler.saveSingleSetting('layout', self.layout)
            self.initScreenLayout2()
        else:
            self.layout = 1
            self.settings_handler.saveSingleSetting('layout', self.layout)
            self.initScreenLayout1()

    def buttonDetectPress(self, dim_hours, off_hours):
        """
        Detects a button press and reacts accordingly.

        Handles display/LED brightness changes, layout selection, and display wake-up.

        Short press during daytime changes display brightness.
        Short press during off hours wakes up the display.

        Long press changes the layout during daytime, dim hours,
        or during an active night wake.

        :param dim_hours: Whether dim hours are active.
        :param off_hours: Whether off hours are active.
        """
        if self.button is None:
            return

        ticks_ms = time.ticks_ms()

        if self.button.value() == 0:
            # Record the start of a new press.
            if self.button_press_time is None:
                self.button_press_time = ticks_ms
                self.button_long_handled = False

            held_ms = time.ticks_diff(ticks_ms, self.button_press_time)

            # Handle the long press once, without waiting for release.
            if held_ms >= 1500 and not self.button_long_handled:
                self.button_long_handled = True

                # Allow layout changes only while the display is lit.
                if not off_hours or self.getNightWake():
                    self.buttonChangeLayout()

        elif self.button_press_time is not None:
            held_ms = time.ticks_diff(ticks_ms, self.button_press_time)
            long_handled = self.button_long_handled

            # Reset the button state on release.
            self.button_press_time = None
            self.button_long_handled = False

            # Ignore brief presses and releases following a long press.
            if held_ms < 100 or long_handled:
                return

            # Ignore long presses missed while the main loop was blocked.
            if held_ms >= 1500:
                return

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

        # Print the time for the current layout.
        if self.layout == 1:
            self.printDateTimeLayout1(date)
        else:
            self.printDateTimeLayout2(date)

    def printDateTimeLayout1(self, date):
        """
        Prints the current time in layout 1.

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
        Prints the current time in layout 2.

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
            # Clamp the temperature to fit the five-character VFD limit.
            temperature = min(999.9, max(-99.9, weather['temperature']))

            # Temperature should always include 1 fraction digit and occupy
            # 5 characters because it can, for example, be '-15.5'.
            temperature = '{:>5.1f}'.format(temperature)

            # Humidity should be rounded and always in range of 0-99,
            # and also always 2 characters. It should never be more
            # than 99% because of available space.
            humidity = '{:>2.0f}'.format(
                min(99, max(0, weather['humidity']))
            )

            # Wind speed should always include 1 fraction digit and occupy
            # 4 characters because it can, for example, be '15.5'.
            wind = min(99.9, max(0, weather['wind']))
            wind = '{:>4.1f}'.format(wind)

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

        temperature = ' --.-'
        humidity = '--'

        if self.sensor:
            try:
                self.sensor.measure()

                # Get calibrated temperature and humidity.
                temperature = self.sensor.temperature() + self.dht_temperature_offset
                humidity = self.sensor.humidity() + self.dht_humidity_offset

                # Clamp the temperature to fit the five-character VFD limit.
                temperature = min(999.9, max(-99.9, temperature))

                # Temperature should always include 1 fraction digit and occupy
                # 5 characters because it can, for example, be '-15.5'.
                temperature = '{:>5.1f}'.format(temperature)

                # Humidity should be rounded and always in range of 0-99,
                # and also always 2 characters. It should never be more
                # than 99% because of available space.
                humidity = '{:>2.0f}'.format(
                    min(99, max(0, humidity))
                )

            # Handle exception if reading failed.
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
        Prints a download icon for 60 seconds after a successful data fetching.

        This icon appears each time after new data is fetched.
        It is used to indicate that Internet data fetching is working.

        This function also takes care of printing another icon if the last
        date and time data fetching failed.

        A time synchronization failure takes priority over the download
        icon and remains visible until synchronization succeeds.
        """
        ticks_ms = time.ticks_ms()

        # Choose position for the active layout.
        if self.layout == 1:
            pos = (4, 3)
        else:
            pos = (2, 3)

        # Show the failure indicator instead of the download icon.
        if self.fetchers.date_last_failed:
            if not self.displayed_fail:
                self.vfd.setCursor(*pos)
                self.vfd.write('X')
                self.displayed_fail = True
                self.displayed_download = False

            # Return during failure, so that the rest of the code is skipped.
            return

        # Reset failure state after successful time synchronization.
        self.displayed_fail = False

        # Show the download icon after successful data fetch.
        if self.fetchers.data_fetched and not self.displayed_download:
            self.vfd.setCursor(*pos)
            self.vfd.writeNamedChar('arrow_right')
            self.displayed_download = True
            self.download_icon_time = ticks_ms

        # Clear the download icon after 60 seconds.
        elif self.displayed_download and time.ticks_diff(ticks_ms, self.download_icon_time) >= (1000 * 60):
            self.vfd.setCursor(*pos)
            self.vfd.write(' ')
            self.displayed_download = False
            self.fetchers.data_fetched = False

    def printWifiIcon(self):
        # Choose position for the active layout.
        if self.layout == 1:
            position = (0, 3)
        else:
            position = (0, 3)

        # Print the Wi-Fi icon.
        self.vfd.setCursor(*position)

        if self.wifi.isConnected() and self.displayed_wifi != 1:
            self.vfd.writeNamedChar('graph')
            self.displayed_wifi = 1

        if not self.wifi.isConnected() and self.displayed_wifi != 0:
            self.vfd.writeNamedChar('not_equal')
            self.displayed_wifi = 0

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

        # Restore the active layout after the animation.
        if self.layout == 1:
            self.initScreenLayout1()
        else:
            self.initScreenLayout2()

        self.resetDisplayedState()

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
        self.wifi.connect()

        # Show the current Wi-Fi connection status before the main loop starts.
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

            # Show Matrix Rain animation on every full hour, e.g., at 5:00.
            self.printMatrixRain()

            # Reconnect Wi-Fi if needed.
            if not self.wifi.isConnected():
                # Indicate no Wi-Fi connection by setting the connection icon
                # before trying to reconnect.
                self.printWifiIcon()
                # Reconnect.
                self.wifi.connect()

            # If Wi-Fi has connected, show an icon.
            self.printWifiIcon()

            # Wait.
            time.sleep(0.1)
