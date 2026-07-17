# PicoBot reporting configuration

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
