import time

# Import for parallel bus.
from noritake_gu_parallel_cpython import NoritakeGuParallel

# Import for serial bus.
# import serial

from noritake_gu import NoritakeGu
from hifi_display import HiFiDisplay

no = None

try:
    # Serial or Parallel - bus.write() method must exist.
    # Serial.
    # serial_bus = serial.Serial('/dev/serial0', baudrate = 38400, bytesize = 8, parity = serial.PARITY_NONE, stopbits = 1)

    # Parallel.
    # GPIO numbers use Raspberry Pi BCM numbering.
    parallel_bus = NoritakeGuParallel(
        [11, 10, 9, 8, 7, 3, 2, 1], 13, 14
    )

    no = NoritakeGu(parallel_bus)
    disp = HiFiDisplay(no)

    # Initialize the display.
    no.clearDisplay()
    no.setBrightness(3)

    # Select Latin 2 for Polish characters support.
    no.characterTable(12)

    # Initialize dual screen for easy screen swapping.
    no.initDualScreen()

    # Print initial elements.
    disp.printInitial()

    # Print track details.
    disp.printTrack(12, 17)
    disp.printTime(115, 242)
    disp.printVolume(37)
    disp.printTitle('Shadow (Album Version with OkinXWX, Lowx, Spacyboi and Tokyo Tears')
    disp.printArtist('Sidewalks And Skeletons')
    
    time.sleep(5)

    disp.showMessage('volume', 67)
    time.sleep(0.2)
    disp.showMessage('volume', 70)
    time.sleep(0.2)
    disp.showMessage('volume', 73)
    time.sleep(0.2)
    disp.showMessage('volume', 76)
    time.sleep(0.2)
    disp.showMessage('volume', 80)
    time.sleep(0.2)
    disp.showMessage('volume', 85)
    time.sleep(0.2)
    disp.showMessage('volume', 88)
    time.sleep(0.2)
    disp.showMessage('volume', 91)
    
    time.sleep(6)
    
    disp.showMessage('text', 'Power Off')
    time.sleep(2)
    no.displayOnOff('off')

    while True:
        time.sleep(1)

except KeyboardInterrupt:
    if no is not None:
        no.scrollingTextStopAll()
        time.sleep(0.3)
        no.clearDisplay()
        no.writeText('Stopped')
