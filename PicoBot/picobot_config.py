# PicoBot reporting configuration

# Wi-Fi mode: 'AP' to create an access point, 'STA' to join an existing network
WIFI_MODE = 'AP'

# Wi-Fi network name (SSID) — used as AP name in AP mode, target network in STA mode
WIFI_SSID = 'picobot-web'

# Wi-Fi password
WIFI_PASSWORD = '12345678'

# Enable HTTPS POST status reporting to the server
SERVER_ENABLE = True

# When True, motors and arm are locked unless server_competition_running is True
SERVER_BRAKE = False

# URL of the server to receive board status via HTTPS POST
REPORT_URL = 'https://example.com/picobot/status'

# Interval in seconds between status POST requests
REPORT_DELAY = 10

# Bearer token for authenticating POST requests; set to None to disable
REPORT_AUTH = None
