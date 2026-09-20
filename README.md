# Noritake Itron CU and GU series VFD driver library

A CPython and MicroPython library for controlling Noritake Itron VFDs.

This library contains two separate modules:

- **[CU series](./CU_Series/README.md)** – a MicroPython module for character displays, for example, 16x2 characters
- **[GU series](./GU_Series/README.md)** – a CPython / MicroPython module for graphical displays, for example, 256x64 pixels.

Each module contains its own separate documentation.

## What is included?

The CU series module contains:
- An API to interact with the VFD
- A Matrix Rain animation demo
- A Digital Clock demo with weather indication
- Readme file with detailed information.

The Gu series module contains:
- An API to interact with the VFD
- A parallel connection class for connecting via parallel (not needed for
  serial connection)
- A Hi-Fi network player screen demo
- Readme file with detailed information.

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

<img src="CU_Series/images/example_supported_displays.jpg" alt="Example supported displays" width="500">

This library module supports the core command sets of Noritake Itron CU series
VFDs and supports the following models:

- 16x2 Characters – CU16024, CU16025, CU16029
- 20x2 Characters – CU20024, CU20025, CU20027, CU20029
- 20x4 Characters – CU20045, CU20049
- 24x2 Characters – CU24025
- 40x2 Characters – CU40025, CU40026
- 40x4 Characters – CU40045
- 40x6 Characters – CU40066

Note: Models usually include factory suffixes (e.g., -UW1J, -UX3J, or -TW200A)
indicating interface or revision details. All variations of the base models
listed above are fully supported (for example, CU20025-UW1J, CU16024-UX3J,
or CU20029-TW200A).

The CU series module was implemented for MicroPython. However, with a bit of work
it is possible to adapt it for regular Python.

For more information about the CU Series module, its connections, and demos see the:  
[CU_Series documentation](./CU_Series/README.md).

## Noritake Itron GU Series

A CPython / MicroPython library module for controlling Noritake Itron GU series
 VFDs, which are graphical displays.

<img src="GU_Series/images/example_supported_display.jpg" alt="Example supported display" width="500">

This library module supports many of the core commands of the Noritake Itron
CU series VFDs and supports the following models:

- 112x16 Pixels – GU112X16G
- 128x32 Pixels – GU128X32D
- 128x64 Pixels – GU128X64, GU128X64D, GU128X64F
- 128x128 Pixels - GU128X128D
- 256x32 Pixels - GU256X32D
- 256x64 Pixels – GU256X64C, GU256X64D, GU256X64E, GU256X64F
- 256x128 Pixels – GU256X128C, GU256X128D, GU256X128E
- 384x32 Pixels – GU384X32L
- 512x32 Pixels - GU512X32H

Note: Models usually include factory suffixes (e.g., '-3900B')
indicating interface or revision details. All variations of the base models
listed above are fully supported (for example, GU256X64D-3900B).

For more information about the GU Series module, its connections, and demos see the:  
[GU_Series documentation](./GU_Series/README.md).

## Noritake Datasheets

You can find the Noritake Datasheets for the VFDs here:
- [https://www.noritake-itron.jp/eng/cs/dl_spec/](https://www.noritake-itron.jp/eng/cs/dl_spec/)

Due to the copyright restrictions, they cannot be included in this repository.