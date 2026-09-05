# Noritake Itron CU and GU series VFD driver library

A MicroPython library for controlling Noritake Itron VFDs.

This project contains two modules which provide support for:
- **CU series** - character displays, for example 16x2 characters
- **GU series** - graphical displays, for example 256x64 pixels

The CU series module also contains:
- Matrix Rain animation demo
- Digital Clock demo with weather indication.

The library was implemented for MicroPython, however, with a bit of work
it is possible to adjust it for a regular Python.

## Some background

I really liked VFD displays from the times when they were the industry standard
in 1990–2010, before OLED was invented. I often miss their style in newer
products.

I decided to custom-build the following IoT devices:
- VFD internet-connected digital clocks to use at home and at work, showing time and weather
- VFD status displays for my Home Lab
- Network players with Bluetooth/AirPlay/etc with integrated VFDs.

For the clocks and home lab I have used CU series displays, while for the
network players I have used GU series 256x64 display.

## Noritake Itron CU Series

A MicroPython library module for controlling Noritake Itron CU series VFDs,
which are character-based displays.

## Noritake Itron GU Series

The GU series part of the library is currently being in development.