import time
import network
import requests
from machine import RTC

# Dots on the start are required for RPi Pico/MicroPython boards.
from .clock_digits import ClockDigits
from .matrix_rain import MatrixRain

# Import clock_config_local.py if user has created it.
try:
    from . import clock_config_local as config
# Otherwise import clock_config.py (assuming the user has customized it).
except ImportError:
    from . import clock_config as config

class ClockTemp:
    """
    Displays a local time clock and local weather data.
    """

    def __init__(self, vfd, lines, cols):
        # Display details.
        self.vfd = vfd
        self.lines = lines
        self.cols = cols

        # Large digits.
        self.digits = ClockDigits(self.vfd)

        # RTC used by the clock feature.
        self.rtc = RTC()

        # Wi-Fi.
        self.wlan = network.WLAN(network.STA_IF)
        self.ssid = config.wifi_ssid
        self.password = config.wifi_password
        self.wifi_last_attempt = None
        self.wifi_retry_interval = 10 * 1000

        # Time settings.
        self.timeapi_api_key = config.time_api_key
        self.timezone = config.time_timezone

        # Time fetching.
        # Stores the last date synchronization time in ms.
        self.date_last_fetch =  None
        self.date_last_attempt = None
        # 2-hour interval converted to milliseconds.
        # This low interval is needed for daylight savings time changes.
        self.date_fetch_interval = 2 * 60 * 60 * 1000

        # Weather settings.
        self.weather_api_key = config.weather_api_key
        self.weather_city = config.weather_city
        self.weather_unit = config.weather_unit

        # Weather fetching.
        # Stores the last weather synchronization time in ms.
        self.weather_last_fetch =  None
        self.weather_last_attempt = None
        # 10-minutes interval converted to milliseconds.
        self.weather_fetch_interval = 10 * 60 * 1000

        # Fetched weather.
        self.weather = {
            'temperature': 0,
            'humidity': 0,
            'conditions': '',
            'success': False,
        }

        # Failed API requests are retried after one minute.
        self.api_retry_interval = 60 * 1000
        self.api_timeout = 10

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

    def urlEncode(self, value):
        """
        Encodes a string to be used in a URL.

        :param value: The string to encode.

        :return: The encoded string.
        """
        encoded = []

        for byte in str(value).encode('utf-8'):
            is_unreserved = (
                ord('A') <= byte <= ord('Z') or
                ord('a') <= byte <= ord('z') or
                ord('0') <= byte <= ord('9') or
                byte in (ord('-'), ord('.'), ord('_'), ord('~'))
            )

            if is_unreserved:
                encoded.append(chr(byte))
            else:
                encoded.append('%{:02X}'.format(byte))

        return ''.join(encoded)

    def urlGetJson(self, url, params = None):
        """
        Gets JSON from a URL.

        :param url: The URL to get JSON from.
        :param params: The parameters to include in the URL.

        :return: The JSON data or False if the request failed.
        """
        if params:
           url = url.rstrip('?') + '?'

           for key, value in params.items():
               url += key + '=' + self.urlEncode(value) + '&'

           url = url.rstrip('&')

        response = requests.get(url, timeout = self.api_timeout)
        try:
            if response.status_code == 200:
                return response.json()

            return False
        finally:
            if response is not None:
                response.close()

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

    def fetchDateTime(self):
        """
        Fetches the current date from the https://gateway.timeapi.world/ API.
        """
        print('Fetching date and time from the Internet.')

        # The timeapi.world gateway endpoint url.
        url = f'https://gateway.timeapi.world/timezone/{self.timezone}'

        headers = {
            'x-rapidapi-key': self.timeapi_api_key,
            'x-rapidapi-host': 'world-time-api3.p.rapidapi.com',
            'Content-Type': 'application/json'
        }

        self.date_last_attempt = time.ticks_ms()
        response = None

        try:
            # Send the GET request with the required headers.
            response = requests.get(url, headers = headers, timeout = self.api_timeout)

            if response.status_code == 200:
                data = response.json()
                datetime = data['datetime']

                # Parse the ISO 8601 datetime response string.
                year = int(datetime[0:4])
                month = int(datetime[5:7])
                day = int(datetime[8:10])
                hour = int(datetime[11:13])
                minute = int(datetime[14:16])
                second = int(datetime[17:19])

                # The API uses 0 for Sunday to 6 for Saturday.
                # RTC expects 0 for Monday to 6 for Sunday.
                api_dow = data['day_of_week']
                rtc_dow = 6 if api_dow == 0 else api_dow - 1

                # Set the system time.
                self.rtc.datetime(
                    (year, month, day, rtc_dow, hour, minute, second, 0)
                )

                # Save the timestamp of the successful synchronization.
                self.date_last_fetch = time.ticks_ms()

                response.close()
                print('Synchronized date and time.')
                return True

            else:
                response.close()
                print('Failed to synchronize date and time.')
                return False

        except Exception as e:
            if hasattr(response, 'close'):
                response.close()
            print('Date and time synchronization error:', e)
            return False

    def getDateTime(self):
        """
        Gets the current date and time from the hardware RTC.
        """
        current_ticks = time.ticks_ms()

        # Fetch date and time from the internet if they weren't fetched yet,
        # or if they were fetched more than 2 hours ago.
        if (
            (self.date_last_fetch is None) or
            (time.ticks_diff(current_ticks, self.date_last_fetch)
             >= self.date_fetch_interval)
        ) and (
            (self.date_last_attempt is None) or
            (time.ticks_diff(current_ticks, self.date_last_attempt)
             >= self.api_retry_interval)
        ):
            self.fetchDateTime()

        # Read the current time directly from the hardware RTC.
        hardware_time = self.rtc.datetime()

        # Return the dictionary with the current date and time parts.
        if self.date_last_fetch is not None:
            return {
                'year': str(hardware_time[0]),
                # Fill with leading zeros.
                'month': '{:0>2}'.format(hardware_time[1]),
                'day': '{:0>2}'.format(hardware_time[2]),
                'hour': '{:0>2}'.format(hardware_time[4]),
                'minute': '{:0>2}'.format(hardware_time[5]),
                'second': '{:0>2}'.format(hardware_time[6]),
                'timestamp': time.time(),
                'hour_int': hardware_time[4],
                'minute_int': hardware_time[5],
            }
        else:
            return {
                'year': 0,
                'month': '00',
                'day': '00',
                'hour': '00',
                'minute': '00',
                'second': '00',
                'timestamp': '00',
                'hour_int': 0,
                'minute_int': 0,
            }

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
        date = self.getDateTime()

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

    def fetchWeather(self):
        """
        Fetches the weather data for from the OpenWeatherMap API.
        """
        print('Fetching weather data from the OpenWeatherMap.')

        # The open weather API endpoint url.
        weather_url = 'https://api.openweathermap.org/data/2.5/weather'

        params = {
            'q': self.weather_city,
            'appid': self.weather_api_key,
            'units': self.weather_unit,
        }

        temperature = 0
        humidity = 0
        conditions = ''
        success = False

        self.weather_last_attempt = time.ticks_ms()

        try:
            weather = self.urlGetJson(weather_url, params)

            # Weather API deta structure.
            # timezone => 7200
            # sys => Dict {
            #   type => 2
            #   sunrise => 1787888431
            #   country => 'PL'
            #   id => 2032856
            #   sunset => 1787938467
            # }
            # base => 'stations'
            # main => Dict {
            #   pressure => 1016
            #   feels_like => 23.67
            #   temp_max => 25.86
            #   temp => 24.18
            #   temp_min => 23.13
            #   humidity => 39
            #   sea_level => 1016
            #   grnd_level => 1005
            # }
            # visibility => 10000
            # id => 756135
            # clouds => Dict {
            #   all => 89
            # }
            # coord => Dict {
            #   lon => 21.0118
            #   lat => 52.2298
            # }
            # name => 'Warsaw'
            # cod => 200
            # weather => [
            #   0 => Dict {
            #     id => 804
            #     icon => '04d'
            #     main => 'Clouds'
            #     description => 'overcast clouds'
            #   }
            # ]
            # dt => 1787930328
            # wind => Dict {
            #   speed => 5.14
            #   deg => 130
            # }

            if weather and isinstance(weather, dict):
                temperature = round(weather['main']['temp'], 1)
                humidity = round(weather['main']['humidity'])
                conditions = weather['weather'][0]['main']
                success = True

                # Save the timestamp of the successful synchronization.
                self.weather_last_fetch = time.ticks_ms()
                print('Fetched weather data from OpenWeatherMap.')

            else:
                print('Failed to fetch weather data from OpenWeatherMap.')

        except Exception as e:
            print('Weather synchronization error:', e)

        self.weather = {
            'temperature': temperature,
            'humidity': humidity,
            'conditions': conditions,
            'success': success,
        }

    def getWeather(self):
        """
        Gets the last fetched weather data and refetches if needed.
        """
        current_ticks = time.ticks_ms()

        # Fetch weather from the internet if it wasn't fetched yet,
        # or if it was fetched more than 10 minutes ago.
        if (
            (self.weather_last_fetch is None) or
            (time.ticks_diff(current_ticks, self.weather_last_fetch)
             >= self.weather_fetch_interval)
        ) and (
            (self.weather_last_attempt is None) or
            (time.ticks_diff(current_ticks, self.weather_last_attempt)
             >= self.api_retry_interval)
        ):
            self.fetchWeather()

        # Return the weather data.
        return self.weather

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
        weather = self.getWeather()

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
            date = self.getDateTime()

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
