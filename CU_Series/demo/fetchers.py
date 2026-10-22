import time
import requests
from machine import RTC

# Import config_local.py if user has created it.
try:
    from . import config_local as config
# Otherwise import config.py (assuming the user has customized it).
except ImportError:
    from . import config

class Fetchers:
    """
    Fetches date and weather data from the Internet.

    This is written for MicroPython.
    """

    def __init__(self):
        # RTC used by the date and time functions.
        self.rtc = RTC()

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

        # This is set to true after data was fetched from the Internet.
        # Projects using this class can use it to track whether data was fetched.
        self.data_fetched = False

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

                # Set a flag that will allow checking if any data
                # was recently fetched from the Internet.
                self.data_fetched = True

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
                'timestamp': 0,
                'hour_int': 0,
                'minute_int': 0,
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

                # Set a flag that will allow checking if any data
                # was recently fetched from the Internet.
                self.data_fetched = True

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