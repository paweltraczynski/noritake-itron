class SettingsHandler:
    """
    Reads and writes simple YAML-like settings files.

    Supported settings file format:
    setting_1: 123
    setting_2: abc

    :param filename: The name of the settings file, including extension.
    :param defaults: Default values for settings if the file is missing.
    They should be provided as a dictionary where keys are setting names
    and values are default values.
    """

    def __init__(self, filename = 'settings.txt', defaults = None):
        self.filename = filename
        self.defaults = defaults or {}
        self.settings_file_lines = []
        
        # Read all settings from the file when the class is instantiated.
        self.settings = self.settingsFileRead()

    def settingsFileRead(self):
        """
        Reads all settings from the file.

        Missing files and invalid values fall back to default values.

        :return: Dictionary with all loaded settings.
        """
        # Start with default settings if there are any.
        settings = self.defaults.copy() if self.defaults else {}

        try:
            with open(self.filename, 'r') as file:
                for line in file:
                    line = line.rstrip('\r\n')
                    self.settings_file_lines.append(line)
                    line_stripped = line.strip()

                    # Skip lines with comments and lines with malformed data.
                    if not line_stripped or line_stripped.startswith('#') or ':' not in line_stripped:
                        continue

                    # Get key and value.
                    key, value = line_stripped.split(':', 1)
                    key = key.strip()
                    value = value.strip()

                    # Skip empty keys.
                    if not key:
                        continue

                    # Add the setting to the dictionary while casting its
                    # value to the appropriate type.
                    settings[key] = self.castValue(value)

        except OSError as e:
            print("Error reading settings: {0}".format(e))

        return settings

    def settingsFileUpdate(self):
        """
        Writes all cached settings to the file.
        """
        written_keys = {}
        settings_file_lines = []

        try:
            with open(self.filename, 'w') as file:
                # Rewrite the original file structure so comments and blank
                # lines stay where the user placed them.
                for line in self.settings_file_lines:
                    line_stripped = line.strip()

                    if not line_stripped or line_stripped.startswith('#') or ':' not in line_stripped:
                        file.write('{0}\n'.format(line))
                        settings_file_lines.append(line)
                        continue

                    key, value = line.split(':', 1)
                    key_stripped = key.strip()

                    # Existing setting lines are replaced in place while
                    # preserving the surrounding comments and blank lines.
                    if key_stripped in self.settings:
                        line = '{0}: {1}'.format(
                            key_stripped,
                            self.formatValue(self.settings[key_stripped])
                        )
                        written_keys[key_stripped] = True

                    file.write('{0}\n'.format(line))
                    settings_file_lines.append(line)

                # Settings added at runtime have no original line to update,
                # so append them after the preserved file content.
                for key in self.settings:
                    if key not in written_keys:
                        line = '{0}: {1}'.format(
                            key,
                            self.formatValue(self.settings[key])
                        )
                        file.write('{0}\n'.format(line))
                        settings_file_lines.append(line)

            self.settings_file_lines = settings_file_lines

        except OSError as e:
            print("Error saving settings: {0}".format(e))

    def getSettings(self):
        """
        Returns all cached settings.

        :return: Dictionary with all cached settings.
        """
        return self.settings

    def saveSingleSetting(self, key, value):
        """
        Writes a single setting while preserving other existing settings.

        :param key: The setting name to write.
        :param value: The setting value to write.
        """
        self.saveManySettings({key: value})

    def saveManySettings(self, values):
        """
        Writes multiple settings while preserving other existing settings.

        :param values: Dictionary of setting names and values to write.
        """
        self.settings.update(values)
        self.settingsFileUpdate()

    def castValue(self, value):
        """
        Casts a setting value based on its text representation.

        The setting value casting is as follows:
        - '1' becomes 1 (an integer)
        - '1.5' becomes 1.5 (a float)
        - 'False' becomes False (a bool)
        - 'True' becomes True (a bool)
        - 'Unquoted string' becomes 'Unquoted string' (a str)
        - "'Single-quoted string'" becomes 'Single-quoted string' (a str)
        - '"Double-quoted string"' becomes 'Double-quoted string' (a str)

        :param value: The value as it was read from the settings file.

        :return: The setting value cast to bool, int, float, or string.
        """
        # Quoted values are always strings.
        if len(value) >= 2:
            if value[0] == "'" and value[-1] == "'":
                return value[1:-1].replace("''", "'")

            if value[0] == '"' and value[-1] == '"':
                return value[1:-1]

        # Boolean values.
        if value.lower() == 'true':
            return True

        if value.lower() == 'false':
            return False

        # Integer values.
        try:
            return int(value)
        except ValueError:
            pass

        # Float values.
        try:
            return float(value)
        except ValueError:
            pass

        # Unquoted string values.
        return value

    def formatValue(self, value):
        """
        Formats a setting value for writing to the settings file.

        :param value: The setting value to format.

        :return: The value that is formatted as text for the settings file.
        """
        # Pack string values with single quotes.
        if isinstance(value, str):
            return "'{0}'".format(value.replace("'", "''"))

        # Pass other values as-is.
        return value
