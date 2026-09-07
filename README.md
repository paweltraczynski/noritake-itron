# Noritake Itron CU and GU series VFD driver library

A MicroPython library for controlling Noritake Itron VFDs.

This project contains two modules which provide support for:
- **CU series** - character displays, for example 16x2 characters
- **GU series** - graphical displays, for example 256x64 pixels

The CU series module also contains:
- Matrix Rain animation demo
- Digital Clock demo with weather indication.

The library was implemented for MicroPython, however, with a bit of work
it is possible to adapt it for regular Python.

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

This library module supports the core command sets of Noritake Itron CU series
VFDs and supports the following models:

- 16x2 Characters – CU16024, CU16025, CU16029
- 20x2 Characters – CU20024, CU20025, CU20027, CU20029
- 20x4 Characters – CU20045, CU20049
- 24x2 Characters – CU24025
- 40x2 Characters – CU40025, CU40026
- 40x4 Characters – CU40045
- 40x6 Characters – CU40066

For more information about the library module, its connections and demos,
see the [CU_Series documentation](./CU_Series/README.md).

## Noritake Itron GU Series

A MicroPython library module for controlling Noritake Itron GU series VFDs,
which are graphical displays.

The GU series part of the library is currently under development.

You can check the current progress in the
[GU_Series documentation](./GU_Series/README.md).

## Noritake Datasheets

You can find the Noritake Datasheets for the VFDs here:
- [https://www.noritake-itron.jp/eng/cs/dl_spec/](https://www.noritake-itron.jp/eng/cs/dl_spec/)