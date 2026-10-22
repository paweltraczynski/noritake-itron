class LargeDigits:
    """
    A class containing big clock characters that occupy 2 rows:
    - large digits (0-9)
    - a large colon displayed between hours and minutes
    - a large dash displayed when the time is not set
    - a removal of a large digit or dash
    - a removal of a colon.
    """
    def __init__(self, disp):
        self.disp = disp

    def largeDigitsInit(self):
        """
        Initializes custom characters used for printing large digits.

        Character shapes based on https://github.com/seanauff/BigNumbers
        """
        disp = self.disp

        # Left side.
        disp.writeCustomChar(0, [0x07, 0x0F, 0x0F, 0x0F, 0x0F, 0x0F, 0x07, 0x00])
        # Upper bar.
        disp.writeCustomChar(1, [0x1F, 0x1F, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        # Right side.
        disp.writeCustomChar(2, [0x1C, 0x1E, 0x1E, 0x1E, 0x1E, 0x1E, 0x1C, 0x00])
        # Left end.
        disp.writeCustomChar(3, [0x0F, 0x07, 0x00, 0x00, 0x00, 0x03, 0x07, 0x00])
        # Lower bar.
        disp.writeCustomChar(4, [0x00, 0x00, 0x00, 0x00, 0x00, 0x1F, 0x1F, 0x00])
        # Right end.
        disp.writeCustomChar(5, [0x1E, 0x1C, 0x00, 0x00, 0x00, 0x18, 0x1C, 0x00])
        # Middle bar.
        disp.writeCustomChar(6, [0x1F, 0x1F, 0x00, 0x00, 0x00, 0x1F, 0x1F, 0x00])
        # Lower end.
        disp.writeCustomChar(7, [0x00, 0x00, 0x00, 0x00, 0x00, 0x07, 0x0F, 0x00])

    def largeDigit(self, digit, column, row = 0):
        """
        Prints a selected large digit at a specified position on the display.

        :param digit: The digit to print, pass 0-9 or colon/dash/erase/erase/erase_colon.
        :param column: The column to print the digit at.
        :param row: The row to print the digit at.
        """
        disp = self.disp
        disp.setCursor(column, row)

        if digit == 0 or digit =='0':
            disp.writeData([0, 1, 2])
            disp.setCursor(column, row + 1)
            disp.writeData([0, 4, 2])

        elif digit == 1 or digit == '1':
            disp.writeData([1, 2, 254])
            disp.setCursor(column, row + 1)
            disp.writeData([7, 2, 4])
            # Replace it with this for a straight line '1'.
            # disp.writeData([254, 2, 254])
            # disp.setCursor(column, row + 1)
            # disp.writeData([254, 2, 254])

        elif digit == 2 or digit == '2':
            disp.writeData([3, 6, 2])
            disp.setCursor(column, row + 1)
            disp.writeData([0, 4, 4])

        elif digit == 3 or digit == '3':
            disp.writeData([3, 6, 2])
            disp.setCursor(column, row + 1)
            disp.writeData([7, 4, 2])

        elif digit == 4 or digit == '4':
            disp.writeData([0, 4, 2])
            disp.setCursor(column, row + 1)
            disp.writeData([254, 254, 2])

        elif digit == 5 or digit == '5':
            disp.writeData([0, 6, 5])
            disp.setCursor(column, row + 1)
            disp.writeData([7, 4, 2])

        elif digit == 6 or digit == '6':
            disp.writeData([0, 6, 5])
            disp.setCursor(column, row + 1)
            disp.writeData([0, 4, 2])

        elif digit == 7 or digit == '7':
            disp.writeData([1, 1, 2])
            disp.setCursor(column, row + 1)
            disp.writeData([254, 254, 2])

        elif digit == 8 or digit == '8':
            disp.writeData([0, 6, 2])
            disp.setCursor(column, row + 1)
            disp.writeData([0, 4, 2])

        elif digit == 9 or digit == '9':
            disp.writeData([0, 6, 2])
            disp.setCursor(column, row + 1)
            disp.writeData([7, 4, 2])

        # Colon printed between hours and minutes.
        elif digit == 'colon':
            disp.write('.')
            disp.setCursor(column, row + 1)
            disp.write('.')

        # Dash printed if the time is not set.
        elif digit == 'dash':
            disp.writeData([4, 4, 254])
            disp.setCursor(column, row + 1)
            disp.writeData([254, 254, 254])

        # Erases digit/dash at a given position.
        elif digit == 'erase':
            disp.write('   ')
            disp.setCursor(column, row + 1)
            disp.write('   ')

        # Erases colon at a given position.
        elif digit == 'erase_colon':
            disp.write(' ')
            disp.setCursor(column, row + 1)
            disp.write(' ')
