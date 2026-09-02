import time
import network
import requests
import urequests
from machine import RTC

from .clock_digits import ClockDigits

# Import clock_config_local.py if user has created it.
try:
    from . import clock_config_local as config
# Otherwise import clock_config.py (assuming the user has customized it).
except ImportError:
    from . import clock_config as config

class ClockTemp:
    """
    Displays a local time clock and a local temperature.
    """

    def __init__(self, vfd, lines, cols):
        # VFD details.
        self.vfd = vfd
        self.lines = lines
        self.cols = cols

        # VFD large digits.
        self.digits = ClockDigits(self.vfd)

        # WLAN.
        self.wlan = network.WLAN(network.STA_IF)
        self.ssid = config.wifi_ssid
        self.password = config.wifi_password

        # Time settings.
        self.timeapi_api_key = config.time_api_key
        self.timezone = config.time_timezone

        # Weather settings.
        self.weather_api_key = config.weather_api_key
        self.weather_city = config.weather_city
        self.weather_unit = config.weather_unit

        # RTC.
        self.rtc = RTC()
        # Stores the last date synchronization time in ms.
        self.date_last_fetch =  None
        # 6-hour interval converted to milliseconds.
        self.date_fetch_interval = 6 * 60 * 60 * 1000

        # Fetched weather.
        self.weather = {
            'temperature': 0,
            'humidity': 0,
            'conditions': '',
            'success': False,
        }
        # Stores the last weather synchronization time in ms.
        self.weather_last_fetch =  None
        # 10-minutes interval converted to milliseconds.
        self.weather_fetch_interval = 10 * 60 * 1000

        # Track last displayed time and weather.
        # This is used for preventing writes to the VFD when the time
        # or weather did not change.
        self.displayed_time = None
        self.displayed_temperature = None
        self.displayed_humidity = None

    def connectWifi(self):
        """
        Connects to the Wi-Fi network.
        """
        self.wlan.active(True)
        self.wlan.connect(self.ssid, self.password)

        # Indicate that connection is in progress.
        self.vfd.clearDisplay()
        self.vfd.setCursor(0, 0)
        self.vfd.write('Connecting Wi-Fi')
        print('Trying to connect to Wi-Fi...')

        while not self.wlan.isconnected():
            time.sleep(1)

        # Indicate successful connection.
        self.vfd.clearDisplay()
        self.vfd.setCursor(0, 0)
        self.vfd.write('Wi-Fi connected')
        print('Established Wi-Fi connection.')
        time.sleep(1.5)

    def urlEncode(self, string):
       """
       Encodes a string to be used in a URL.

       :param string: The string to encode.

       :return: The encoded string.
       """
       encoded_string = ''

       for character in str(string):
           if character.isalpha() or character.isdigit():
               encoded_string += character
           else:
               encoded_string += f"%{ord(character):x}"

       return encoded_string

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

       response = urequests.get(url)

       if response.status_code == 200:
           return response.json()
       else:
           return False

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

        try:
            # Send the GET request with the required headers.
            response = requests.get(url, headers = headers)

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
            print('Date and time synchronization error:', e)
            return False

    def getDateTime(self):
        """
        Gets the current date and time from the hardware RTC.
        """
        current_ticks = time.ticks_ms()

        # Fetch date and time from the internet if they weren't fetched yet,
        # or if they were fetched more than 6 hours ago.
        if (self.date_last_fetch is None) or (
            time.ticks_diff(current_ticks, self.date_last_fetch)
            >= self.date_fetch_interval
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
            }
        else:
            return {
                'year': 0,
                'month': 0,
                'day': 0,
                'hour': 0,
                'minute': 0,
                'second': 0,
                'timestamp': 0,
                'hour_int': 0,
            }

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

        weather = self.urlGetJson(weather_url, params)

        temperature = 0
        humidity = 0
        conditions = ''
        success = False

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

        if weather:
            temperature = round(weather['main']['temp'], 1)
            humidity = round(weather['main']['humidity'], 0)
            conditions = weather['weather'][0]['main']
            success = True

            # Save the timestamp of the successful synchronization.
            self.weather_last_fetch = time.ticks_ms()
            print('Fetched weather data from OpenWeatherMap.')

        else:
            print('Failed to fetch weather data from OpenWeatherMap.')

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
        if (self.weather_last_fetch is None) or (
            time.ticks_diff(current_ticks, self.weather_last_fetch)
            >= self.weather_fetch_interval
        ):
            self.fetchWeather()

        # Return the weather data.
        return self.weather

    def screenInit(self):
        """
        Initializes VFD large digits and prints message and then placeholders.
        """
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

        """
        self.connectWifi()
        self.screenInit()

        while True:
            # Get the time.
            date = self.getDateTime()

            # Print the time if it is set.
            if date['year'] != 0:
                time_formatted = '{hour}:{minute}'.format(hour = date['hour'], minute = date['minute'])

                # Do so only if it has changed since the last print.
                if self.displayed_time != time_formatted:
                    self.digits.largeDigit(date['hour'][0], 0)
                    self.digits.largeDigit(date['hour'][1], 3)
                    self.digits.largeDigit(date['minute'][0], 7)
                    self.digits.largeDigit(date['minute'][1], 10)
                    self.displayed_time = time_formatted

                # Blinking colon between hours and minutes.
                if (date['timestamp'] % 2) == 0:
                    self.digits.largeDigit('colon', 6)
                else:
                    self.digits.largeDigit('erase_colon', 6)

            # If time is not set, then print dashes and static colon.
            else:
                if self.displayed_time != '--:--':
                    self.digits.largeDigit('dash', 0)
                    self.digits.largeDigit('dash', 3)
                    self.digits.largeDigit('dash', 7)
                    self.digits.largeDigit('dash', 10)
                    self.digits.largeDigit('colon', 6)
                    self.displayed_time = '--:--'

            # Get the weather.
            weather = self.getWeather()

            # Print the weather if it is set.
            if weather['success']:
                temperature = weather['temperature']
                humidity = weather['humidity']

                # Temperature should be rounded and always occupying 3
                # characters because it can for example be 5 or -12.
                temperature = '{:>3.0f}'.format(temperature)

                # Humidity should be rounded and always in range of 0-99,
                # and also always 2 characters.
                # Humidity should never be more than 99% because of
                # available space.
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

            # Wipe out the weather if it is not set.
            else:
                if self.displayed_temperature != '--':
                    self.vfd.setCursor(13, 0)
                    self.vfd.writeText(' --')
                    self.displayed_temperature = '--'

                self.vfd.setCursor(14, 1)
                self.vfd.writeText('--')

            # Screen dimming at night (requires parallel connection).
            try:
                if date['year'] != 0:
                    hour = date['hour']

                    # TODO: This doesnt work.
                    # TODO: This should also work at other hours so that it dims when plugged to power at night.
                    # TODO: Dont send writes if the brightness did not change.
                    if hour == config.vfd_on_hour:
                        self.vfd.setBrightness(4)
                    elif hour == config.vfd_dim_hour:
                        self.vfd.setBrightness(2)
                    elif hour == config.vfd_off_hour:
                        self.vfd.setBrightness(0)
            except:
                pass

            # Reconnect Wi-Fi if needed.
            if not self.wlan.isconnected():
                self.connectWifi()

            time.sleep(0.1)
            # TODO: Show matrix animation once in an hour.
