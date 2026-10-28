import time
import network

class WiFiConnection:
    """
    Manages a Wi-Fi connection.

    :param ssid: The Wi-Fi network name.
    :param password: The Wi-Fi network password.
    :param retry_interval: Minimum time between connection attempts, in seconds.
    """

    def __init__(self, ssid, password, retry_interval = 10):
        self.wlan = network.WLAN(network.STA_IF)
        self.ssid = ssid
        self.password = password
        self.wifi_last_attempt = None
        self.wifi_retry_interval = retry_interval * 1000

    def connect(self):
        """
        Connects to the Wi-Fi network, retries if the SSID is unavailable.
        """
        current_ticks = time.ticks_ms()

        # Do not retry connecting more often than the configured interval.
        if (
            self.wifi_last_attempt is not None and
            time.ticks_diff(current_ticks, self.wifi_last_attempt)
            < self.wifi_retry_interval
        ):
            return False

        self.wifi_last_attempt = current_ticks
        self.wlan.active(True)

        # Initiate a Wi-Fi connection.
        try:
            self.wlan.connect(self.ssid, self.password)
        except OSError:
            return False

        # Give this attempt up to 10 seconds.
        for _ in range(10):
            if self.wlan.isconnected():
                break
            time.sleep(1)

        # Because up to 10 seconds might have passed, update the last attempt.
        self.wifi_last_attempt = time.ticks_ms()

        # If the connection failed, then try to disconnect before retrying.
        if not self.wlan.isconnected():
            try:
                self.wlan.disconnect()
            except OSError:
                pass

            print('Wi-Fi unavailable; retrying...')
            return False

        print('Established Wi-Fi connection.')
        return True

    def isConnected(self):
        """
        Returns True if the WLAN interface is connected.
        """
        return self.wlan.isconnected()
