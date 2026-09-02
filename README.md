Noritake Itron VFD driver library
===============

A Python library for controlling Noritake Itron displays:
- **CU series** - character displays, for example 16x2 characters
- **GU series** - graphical displays, for example 256x64 pixels

The library also contains:
- Matrix Rain animation demo
- Digital Clock demo with weather indication.

## Some background

I really liked VFD displays from the times when they were the industry standard
in 1990-2010, before OLED was invented. I often miss their style in newer
products.

I decided to custom-build the following IoT devices:
- VFD internet-connected digital clocks to use at home and at work, showing time and weather
- VFD status displays for my Home Lab
- Network players with Bluetooth/AirPlay/etc with integrated VFDs.

For the clocks and home lab I have used CU series displays, while for the network players
I have used GU series 256x64 display.

## Noritake Itron CU Series
The Noritake Itron VFD character display supported models are:
- CU16025, CU16024, CU16029 - 16x2 characters
- CU20025, CU20024, CU20027, 20x2 characters
- CU20045, CU20049 - 20x4 characters
- CU24025 - 24x2 characters
- CU40025 - 40x2 characters
- CU40045 - 40x4 characters

The library works with both Python and MicroPython, the latter being
implemented by default.

To use the library with a regular non-micro Python, like on Raspberry Pi 5
or newer, you need do small adjustments in the `main_gpio.py` or `main_i2c.py` file.
They are explained in these files.

### Connections

You can connect VFD to your MicroPython board (e.g. Raspberry Pico, ESP32, etc.)
using either parallel/GPIO connection or I<sup>2</sup>C connection.

When using parallel/GPIO connection you need to import the
`noritake_cu_gpio.py` file. An example of the main script when using parallel/GPIO is shown in the
`main_gpio.py`.

When using I<sup>2</sup>C connection you need to import the
`noritake_cu_i2c.py` file. An example of the main script when using I<sup>2</sup>C is shown in the
`main_i2c.py`.

### Parallel/GPIO connection

To connect using parallel/GPIO, connect the VFD directly to GPIO port
using these cables:

- pin 1 - VSS - Ground
- pin 2 - VDD - 5V
- pin 3 - Contrast - not used by VFDs
- pin 4 - RS (Register Select) - connect to GPIO
- pin 5 - R/W (Read/Write) - connect to ground since the library writes only
- pin 6 - E (Enable) - connect to GPIO
- pins 7-10 - DB (Data Bus) - lower four bits for 8-bit operation, if you are
  using 4-bit mode then leave these unconnected
- pins 11-14 - DB (Data Bus) - upper four bits for 4-bit or 8-bit communication,
  connected to GPIO

The following picture shows this kind of connection:

TODO: Image coming soon

### I<sup>2</sup>C connection

To connect using I<sup>2</sup>C you need to use a HD44780 compatible
I<sup>2</sup>C converter like the one shown here:

<img src="https://cdn3.botland.store/74254-pdt_540/i2c-converter-for-hd44780-lcd-display.jpg" alt="I2C converter for HD44780 compatible displays" width="300" height="300">

The converter gets connected to the VFD using its 14-16 pins header.
The 4 pins on the side of the converted connect directly to the GPIO port using these cables:

- pin 1 - GND - Ground
- pin 2 - VCC - 5V
- pin 3 - SDA - I<sup>2</sup>C data line on your Python board
- pin 4 - SCL - I<sup>2</sup>C clock line on your Python board

The following picture shows this kind of connection:

TODO: Image coming soon

### Demo scripts

There are two demo scripts that you can run and customize to your needs:
- Matrix Rain animation (`matrix_rain.py`)
- Digital Clock (`clock.py`, `clock_digits.py` and `clock_config.py`)

To test if everything works you can run the Matrix Rain demo script first
as it has no configuration and does not rely on the internet connection
and third party APIs.

### Matrix Rain animation demo

To run the Matrix Rain animation you need to do changes in the `main_gpio.py` or
in `main_i2c.py` depending on what connection type you are using.

Adjust the numer of lines and columns that you VFD has:
```python
# Define the number of lines and columns in the display.
lines = 2
cols = 16
```

Uncomment the code:
```python
# rain = MatrixRain(vfd, lines, cols)
# rain.animate()
```

Then run the file  
(in Raspberry Pico you can rename the file to `main.py` so that it runs 
automatically).

You can see the result of working Matrix Rain below:

TODO: Image coming soon

### Digital Clock demo

To run the Digital Clock, first you need to do the same changes as explained
in the Matrix Rain animation demo section, except this time you would have
to uncomment the code related to the clock functionality:
```python
# clock = ClockTemp(vfd, lines, cols)
# clock.keepRunning()
```

Then you need to copy `clock_config.py` to `clock_config_local.py` and do
edits in the copy:
- `wifi_ssid` - provide the name of your Wi-Fi network
- `wifi_password` - provide the password to your Wi-Fi network
- `time_api_key` - the system needs to access timeapi.world API to get the timezone dependant time
- `time_timezone` - provide the timezone for which to get the time
- `weather_api_key` - the system needs to access OpenWeatherMap API to get the weather data
- `weather_city` - provide the city for which to show the weather
- `weather_unit` - set either to 'metric' or 'imperial'
- `vfd_dim_hour` - at what hour the VFD should dim because its early night
- `vfd_off_hour` - at what hour the VFD should turn off because its late night
- `vfd_on_hour` - at what hour in the morning the VFD should turn on again

When you edit configuration you need to obtain API keys for timeapi.world and
for OpenWeatherMap. Links are provided in the configuration file.

## Noritake Itron GU Series

The GU series part of the library is currently being in development.