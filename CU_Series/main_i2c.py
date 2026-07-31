from machine import Pin, I2C
import utime
from noritake_cu_i2c import NoritakeI2C
from demo.matrix_rain import MatrixRain

# Allow time for the display to become ready for receiving commands.
utime.sleep(1)

# Define the number of lines and columns in the display.
lines = 2
cols = 16

# Initialize Noritake VFD.
i2c = I2C(0, scl = Pin(1), sda = Pin(0))

vfd = NoritakeI2C(
    i2c = i2c,
    i2c_addr = 0x27,
    num_lines = lines,
    num_columns = cols
)

# Run Matrix Rain animation for GPIO/I2C.
rain = MatrixRain(vfd = vfd, lines = lines, cols = cols)
rain.animate()
