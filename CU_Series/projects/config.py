# Copy this file to config_local.py and do your changes there.
# Alternatively, you can apply your config changes directly in this file.

# Wi-Fi configuration.
wifi_ssid = 'ssid'
wifi_password = 'password'

# API's configuration.
# To get the TimeAPI World API key, sign up at:
# https://timeapi.world/
# https://rapidapi.com/sleeyax/api/world-time-api3
# https://rapidapi.com/sleeyax/api/world-time-api3/playground/
time_api_key = 'your_api_key'
time_timezone = 'Europe/Warsaw'

# To get the OpenWeatherMap API key, sign up at:
# https://home.openweathermap.org/
# https://home.openweathermap.org/api_keys
weather_api_key = 'your_api_key'
weather_city = 'Warsaw'
weather_unit = 'metric'

# Digital clock / Weather clock configuration.
# Display night hours dimming.
display_dim_start_hour = 20
display_dim_end_hour = 0
display_off_start_hour = 0
display_off_end_hour = 8

# VFD Matrix Rain animation at every full hour.
# Set the animation duration in seconds or set to 0 to disable it completely.
matrix_rain_duration = 30

# Matrix Rain configuration.
matrix_chars_block_min_length = 6
matrix_chars_block_max_length = 14
matrix_spaces_block_min_length = 2
matrix_spaces_block_max_length = 4
matrix_animation_interval = 0.15

# Weather clock configuration.
# DHT22 calibration offsets.
dht_temperature_offset = 0.0
dht_humidity_offset = 0.0
