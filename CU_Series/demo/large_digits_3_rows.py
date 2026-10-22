class LargeDigits:
    """
    A class containing big clock characters that occupy 3 rows:
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
        """
        disp = self.disp

        # Top right square.
        disp.writeCustomChar(0, [0x07, 0x07, 0x07, 0x00, 0x00, 0x00, 0x00, 0x00])
        # Top left-to-right rectangle.
        disp.writeCustomChar(1, [0x1f, 0x1f, 0x1f, 0x00, 0x00, 0x00, 0x00, 0x00])
        # Corner top left.
        disp.writeCustomChar(2, [0x1f, 0x1f, 0x1f, 0x1c, 0x1c, 0x1c, 0x1c, 0x1c])
        # Corner top right.
        disp.writeCustomChar(3, [0x1f, 0x1f, 0x1f, 0x07, 0x07, 0x07, 0x07, 0x07])
        # Edge left.
        disp.writeCustomChar(4, [0x1c, 0x1c, 0x1c, 0x1c, 0x1c, 0x1c, 0x1c, 0x1c])
        # Edge right.
        disp.writeCustomChar(5, [0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07])
        # Colon.
        disp.writeCustomChar(6, [0x00, 0x00, 0x00, 0x00, 0x0E, 0x0E, 0x0E, 0x00])

    def largeDigit(self, digit, column, row = 1):
        """
        Prints a selected large digit at a specified position on the display.
        
        Requires 4 lines display, because the digits take 3 lines.
        It's best to print them at row 1, but row 2 will also work.

        :param digit: The digit to print, pass 0-9 or colon/dash/erase/erase/erase_colon.
        :param column: The column to print the digit at.
        :param row: The row to print the digit at.
        """
        disp = self.disp
        disp.setCursor(column, row)

        if digit == 0 or digit =='0':
            disp.write([2, 3])
            disp.setCursor(column, row + 1)
            disp.write([4, 5])
            disp.setCursor(column, row + 2)
            disp.write([1, 1])

        elif digit == 1 or digit == '1':
            disp.write([0, 4])
            disp.setCursor(column, row + 1)
            disp.write([32, 4])
            disp.setCursor(column, row + 2)
            disp.write([0, 1])

        elif digit == 2 or digit == '2':
            disp.write([1, 3])
            disp.setCursor(column, row + 1)
            disp.write([2, 1])
            disp.setCursor(column, row + 2)
            disp.write([1, 1])

        elif digit == 3 or digit == '3':
            disp.write([1, 3])
            disp.setCursor(column, row + 1)
            disp.write([0, 3])
            disp.setCursor(column, row + 2)
            disp.write([1, 1])

        elif digit == 4 or digit == '4':
            disp.write([4, 5])
            disp.setCursor(column, row + 1)
            disp.write([1, 3])
            disp.setCursor(column, row + 2)
            disp.write([32, 0])

        elif digit == 5 or digit == '5':
            disp.write([2, 1])
            disp.setCursor(column, row + 1)
            disp.write([1, 3])
            disp.setCursor(column, row + 2)
            disp.write([1, 1])

        elif digit == 6 or digit == '6':
            disp.write([2, 1])
            disp.setCursor(column, row + 1)
            disp.write([2, 3])
            disp.setCursor(column, row + 2)
            disp.write([1, 1])

        elif digit == 7 or digit == '7':
            disp.write([1, 3])
            disp.setCursor(column, row + 1)
            disp.write([32, 5])
            disp.setCursor(column, row + 2)
            disp.write([32, 0])

        elif digit == 8 or digit == '8':
            disp.write([2, 3])
            disp.setCursor(column, row + 1)
            disp.write([2, 3])
            disp.setCursor(column, row + 2)
            disp.write([1, 1])

        elif digit == 9 or digit == '9':
            disp.write([2, 3])
            disp.setCursor(column, row + 1)
            disp.write([1, 3])
            disp.setCursor(column, row + 2)
            disp.write([1, 1])

        # Colon printed between hours and minutes.
        elif digit == 'colon':
            disp.write(6)
            disp.setCursor(column, row + 1)
            disp.write(6)
            disp.setCursor(column, row + 2)
            disp.write(' ')

        # Dash printed if the time is not set.
        elif digit == 'dash':
            disp.write([32, 32])
            disp.setCursor(column, row + 1)
            disp.write([1, 1])
            disp.setCursor(column, row + 2)
            disp.write([32, 32])

        # Erases digit/dash at a given position.
        elif digit == 'erase':
            disp.write([32, 32])
            disp.setCursor(column, row + 1)
            disp.write([32, 32])
            disp.setCursor(column, row + 2)
            disp.write([32, 32])

        # Erases colon at a given position.
        elif digit == 'erase_colon':
            disp.write(' ')
            disp.setCursor(column, row + 1)
            disp.write(' ')
            disp.setCursor(column, row + 2)
            disp.write(' ')