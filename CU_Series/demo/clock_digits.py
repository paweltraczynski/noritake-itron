class ClockDigits:
    """
    A class containing VFD clock characters:
    - large digits (0-9)
    - a large colon displayed between hours and minutes
    - a large dash displayed when the time is not set.
    """
    def __init__(self, vfd):
        self.vfd = vfd

    def largeDigitsInit(self):
        """
        Initializes custom characters used for printing large digits.

        Character shapes based on https://github.com/seanauff/BigNumbers
        """
        vfd = self.vfd

        # Left side.
        vfd.writeCustomChar(0, [0x07, 0x0F, 0x0F, 0x0F, 0x0F, 0x0F, 0x07, 0x00])
        # Upper bar.
        vfd.writeCustomChar(1, [0x1F, 0x1F, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        # Right side.
        vfd.writeCustomChar(2, [0x1C, 0x1E, 0x1E, 0x1E, 0x1E, 0x1E, 0x1C, 0x00])
        # Left end.
        vfd.writeCustomChar(3, [0x0F, 0x07, 0x00, 0x00, 0x00, 0x03, 0x07, 0x00])
        # Lower bar.
        vfd.writeCustomChar(4, [0x00, 0x00, 0x00, 0x00, 0x00, 0x1F, 0x1F, 0x00])
        # Right end.
        vfd.writeCustomChar(5, [0x1E, 0x1C, 0x00, 0x00, 0x00, 0x18, 0x1C, 0x00])
        # Middle bar.
        vfd.writeCustomChar(6, [0x1F, 0x1F, 0x00, 0x00, 0x00, 0x1F, 0x1F, 0x00])
        # Lower end.
        vfd.writeCustomChar(7, [0x00, 0x00, 0x00, 0x00, 0x00, 0x07, 0x0F, 0x00])

    def largeDigit(self, digit, column, row = 0):
        """
        Prints a selected large digit at a specified position on the display.

        :param digit: The digit to print, pass 0-9 or colon/dash/erase/erase/erase_colon.
        :param column: The column to print the digit at.
        :param row: The row to print the digit at.
        """
        vfd = self.vfd
        vfd.setCursor(column, row)

        if digit == 0 or digit =='0':
            vfd.writeData([0, 1, 2])
            vfd.setCursor(column, row + 1)
            vfd.writeData([0, 4, 2])

        elif digit == 1 or digit == '1':
            vfd.writeData([1, 2, 254])
            vfd.setCursor(column, row + 1)
            vfd.writeData([7, 2, 4])

        elif digit == 2 or digit == '2':
            vfd.writeData([3, 6, 2])
            vfd.setCursor(column, row + 1)
            vfd.writeData([0, 4, 4])

        elif digit == 3 or digit == '3':
            vfd.writeData([3, 6, 2])
            vfd.setCursor(column, row + 1)
            vfd.writeData([7, 4, 2])

        elif digit == 4 or digit == '4':
            vfd.writeData([0, 4, 2])
            vfd.setCursor(column, row + 1)
            vfd.writeData([254, 254, 2])

        elif digit == 5 or digit == '5':
            vfd.writeData([0, 6, 5])
            vfd.setCursor(column, row + 1)
            vfd.writeData([7, 4, 2])

        elif digit == 6 or digit == '6':
            vfd.writeData([0, 6, 5])
            vfd.setCursor(column, row + 1)
            vfd.writeData([0, 4, 2])

        elif digit == 7 or digit == '7':
            vfd.writeData([1, 1, 2])
            vfd.setCursor(column, row + 1)
            vfd.writeData([254, 254, 2])

        elif digit == 8 or digit == '8':
            vfd.writeData([0, 6, 2])
            vfd.setCursor(column, row + 1)
            vfd.writeData([0, 4, 2])

        elif digit == 9 or digit == '9':
            vfd.writeData([0, 6, 2])
            vfd.setCursor(column, row + 1)
            vfd.writeData([7, 4, 2])

        # Colon printed between hours and minutes.
        elif digit == 'colon':
            vfd.write('.')
            vfd.setCursor(column, row + 1)
            vfd.write('.')

        # Dash printed if the time is not set.
        elif digit == 'dash':
            vfd.writeData([4, 4, 254])
            vfd.setCursor(column, row + 1)
            vfd.writeData([254, 254, 254])

        # Erases digit at a given position.
        elif digit == 'erase':
            vfd.write('   ')
            vfd.setCursor(column, row + 1)
            vfd.write('   ')

        # Erases colon at a given position.
        elif digit == 'erase_colon':
            vfd.write(' ')
            vfd.setCursor(column, row + 1)
            vfd.write(' ')
