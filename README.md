# PicoBot Web Control

A MicroPython application that turns a **Raspberry Pi Pico W** into a Wi-Fi access point and serves a touch-friendly web interface for controlling a 4-wheel robot with a 3-axis servo arm.  
Optionally the robot reports its status to an external HTTPS server at a configurable interval and receives back competition-state commands.

---

## Table of Contents

1. [Hardware Requirements](#hardware-requirements)
2. [Software Overview](#software-overview)
3. [File Structure](#file-structure)
4. [Configuration](#configuration)
5. [Installing to Raspberry Pi Pico W](#installing-to-raspberry-pi-pico-w)
6. [Connecting to the Robot](#connecting-to-the-robot)
7. [Controlling the Robot from a Phone Browser](#controlling-the-robot-from-a-phone-browser)
8. [Server Reporting Feature](#server-reporting-feature)
9. [Server Command Bit Flags](#server-command-bit-flags)

---

## Hardware Requirements

| Component | Details |
|-----------|---------|
| Microcontroller | Raspberry Pi Pico W |
| Motor driver board | PCA9685-based PWM board (I²C address `0x40`, I²C0: SDA GP20, SCL GP21) |
| Drive motors | 4× DC motors — Left Front, Left Back, Right Front, Right Back |
| Arm servo controller | PCA9685-based PWM board (I²C1: SDA GP2, SCL GP3) |
| Arm servos | 3× servo motors on channels 0 (base), 1 (arm), 2 (claw) |
| Power supply | Suitable battery pack for motors and Pico W |

---

## Software Overview

The application runs entirely on the Pico W under **MicroPython**.  
When powered on it:

1. Creates a Wi-Fi access point (or connects to one in STA mode) using the SSID and password set in `picobot_config.py`.
2. Opens an HTTP server on port **80** at IP **`192.168.4.1`**.
3. Serves a touch-optimised control page to any browser on the same Wi-Fi network.
4. *(Optional)* Periodically POSTs the board status to a remote HTTPS server and reads back a single integer that controls competition state flags.

The event loop is non-blocking: the socket has a 1-second accept timeout so the periodic HTTPS report fires on schedule even when no browser client is connected.

---

## File Structure

```
picobot-web-control/
├── main.py                  # Entry point loaded by MicroPython on boot
└── PicoBot/
    ├── picobot_config.py    # All user-facing configuration variables
    ├── picobot_main.py      # Main application: web server + event loop
    ├── picobot.py           # PicoBot high-level class (motors + arm)
    ├── picobot_motors.py    # Low-level motor driver (PCA9685 via I²C0)
    ├── picobot_arm.py       # Servo arm driver (PCA9685 via I²C1)
    └── pca9685.py           # PCA9685 PWM chip driver (arm board)
```

`main.py` adds `PicoBot/` to the Python path and imports everything from `picobot_main.py`, so MicroPython automatically runs the application on every boot.

---

## Configuration

All settings live in **`PicoBot/picobot_config.py`**. Edit this file before uploading to the board.

```python
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
```

### Variable Reference

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `WIFI_MODE` | `str` | `'AP'` | `'AP'` — Pico W creates its own access point. `'STA'` — Pico W connects to an existing Wi-Fi network. |
| `WIFI_SSID` | `str` | `'picobot-web'` | Network name. In AP mode this is the name of the hotspot; in STA mode this is the network to join. |
| `WIFI_PASSWORD` | `str` | `'12345678'` | Password for the Wi-Fi network. |
| `SERVER_ENABLE` | `bool` | `True` | Enable/disable HTTPS status reporting entirely. When `False` the server status bar is also hidden from the web UI. |
| `SERVER_BRAKE` | `bool` | `False` | When `True`, all motor and arm commands are blocked until the server signals that the competition is running (bit 1 of `server_command`). The web UI shows a lock overlay. |
| `REPORT_URL` | `str` | — | Full HTTPS URL that receives the POST request. Must use `https://`. |
| `REPORT_DELAY` | `int` | `10` | Seconds between successive POST requests. |
| `REPORT_AUTH` | `str\|None` | `None` | If set, sent as a Bearer token in the `Authorization` header. Set to `None` to send unauthenticated requests. |

---

## Installing to Raspberry Pi Pico W

### Prerequisites

* [Thonny IDE](https://thonny.org/) **or** the `mpremote` command-line tool.
* MicroPython firmware for Pico W — download the latest `.uf2` from [micropython.org](https://micropython.org/download/RPI_PICO_W/).

### Step 1 — Flash MicroPython firmware

1. Hold the **BOOTSEL** button on the Pico W and connect it to your computer via USB.
2. It mounts as a USB drive called **`RPI-RP2`**.
3. Drag and drop the downloaded `.uf2` file onto the drive.
4. The Pico W reboots automatically into MicroPython.

### Step 2 — Upload the files (Thonny)

1. Open **Thonny**, go to *Tools → Options → Interpreter* and select **MicroPython (Raspberry Pi Pico)**.
2. In the *Files* panel (View → Files), navigate to the `picobot-web-control` folder on your computer.
3. Edit `PicoBot/picobot_config.py` with your desired settings.
4. Upload the files in this order:

   | Local path | Upload to (on Pico W) |
   |------------|----------------------|
   | `main.py` | `/main.py` |
   | `PicoBot/picobot_config.py` | `/PicoBot/picobot_config.py` |
   | `PicoBot/picobot_main.py` | `/PicoBot/picobot_main.py` |
   | `PicoBot/picobot.py` | `/PicoBot/picobot.py` |
   | `PicoBot/picobot_motors.py` | `/PicoBot/picobot_motors.py` |
   | `PicoBot/picobot_arm.py` | `/PicoBot/picobot_arm.py` |
   | `PicoBot/pca9685.py` | `/PicoBot/pca9685.py` |

   To upload a file: right-click it in the local panel → *Upload to /* (create the `/PicoBot/` directory first if needed).

5. Press the **Reset** button or disconnect and reconnect the USB cable. The onboard LED lights up when the access point is active.

### Step 2 (alternative) — Upload with mpremote

```bash
# Install mpremote
pip install mpremote

# Create the PicoBot directory on the device
mpremote mkdir /PicoBot

# Upload all files
mpremote cp main.py :/main.py
mpremote cp PicoBot/picobot_config.py  :/PicoBot/picobot_config.py
mpremote cp PicoBot/picobot_main.py    :/PicoBot/picobot_main.py
mpremote cp PicoBot/picobot.py         :/PicoBot/picobot.py
mpremote cp PicoBot/picobot_motors.py  :/PicoBot/picobot_motors.py
mpremote cp PicoBot/picobot_arm.py     :/PicoBot/picobot_arm.py
mpremote cp PicoBot/pca9685.py         :/PicoBot/pca9685.py

# Soft-reset to start the application
mpremote reset
```

---

## Connecting to the Robot

1. Power on the robot. The onboard LED on the Pico W turns **on** when the access point is ready (usually within 5 seconds).
2. On your phone, go to **Settings → Wi-Fi** and connect to:
   - **Network:** `WIFI_SSID` value from `picobot_config.py` (default: `picobot-web`)
   - **Password:** `WIFI_PASSWORD` value from `picobot_config.py` (default: `12345678`)
3. Open a browser and navigate to **`http://192.168.4.1`**.

> **Note:** Your phone may warn that the network has no internet access. Tap **"Stay connected"** or **"Use this network anyway"** to keep the connection.

---

## Controlling the Robot from a Phone Browser

The web interface is optimised for touchscreens. After opening `http://192.168.4.1` you will see:

### Status Bar *(only when `SERVER_ENABLE = True`)*

A row of three indicators at the top shows the live server state:

| Indicator | Meaning |
|-----------|---------|
| **Server online** | Last POST request succeeded |
| **Competition ready** | Server bit 0 is set — competition is prepared |
| **Competition running** | Server bit 1 is set — competition is actively running |

Each indicator shows **YES** (green) or **NO** (red).

### Movement Controls

A 4×3 grid of large touch buttons covers all drive directions:

| Button | Action |
|--------|--------|
| ↖️ L-Fwd | Left-forward diagonal |
| ⬆️ Forward | All four wheels forward |
| ↗️ R-Fwd | Right-forward diagonal |
| ⬅️ Left | Strafe / turn left |
| ⏹️ STOP | Stop all motors immediately |
| ➡️ Right | Strafe / turn right |
| ↙️ L-Back | Left-backward diagonal |
| ⬇️ Back | All four wheels backward |
| ↘️ R-Back | Right-backward diagonal |
| 🔄 Rot-L | Rotate left on the spot |
| ⏹️ STOP | Stop all motors immediately |
| 🔃 Rot-R | Rotate right on the spot |

Each tap sends a single HTTP request; the robot executes the command and stops after a short delay (0.1 s).

### Arm Controls

Three sliders control the servo arm:

| Slider | Channel | Range |
|--------|---------|-------|
| **Base** | Servo 0 | 0° – 180° |
| **Arm** | Servo 1 | 40° – 140° |
| **Claw** | Servo 2 | 40° – 140° |

Dragging a slider sends the new angle immediately. The servo moves smoothly to the target position.

The **🔄 Reset All** button returns all three servos to 90°.

### Lock Overlay *(when `SERVER_BRAKE = True` and competition is not running)*

When `SERVER_BRAKE` is enabled and `server_competition_running` is `False`, all buttons and sliders are disabled and a grey **🔒 Waiting for competition start** overlay covers the control area. Commands sent directly (e.g. via URL) are also silently ignored by the firmware. Controls unlock automatically the next time the server reports that the competition is running.

---

## Server Reporting Feature

When `SERVER_ENABLE = True`, every `REPORT_DELAY` seconds the robot sends an HTTPS POST request to `REPORT_URL` with a JSON body:

```json
{
  "mac":        "aa:bb:cc:dd:ee:ff",
  "ip":         "192.168.4.1",
  "servo_base": 90,
  "servo_arm":  90,
  "servo_claw": 90,
  "uptime_ms":  12345
}
```

| Field | Description |
|-------|-------------|
| `mac` | MAC address of the Pico W wireless adapter |
| `ip` | IP address of the Pico W on its Wi-Fi network |
| `servo_base` | Current base servo angle in degrees |
| `servo_arm` | Current arm servo angle in degrees |
| `servo_claw` | Current claw servo angle in degrees |
| `uptime_ms` | Milliseconds since boot (`time.ticks_ms()`) |

If `REPORT_AUTH` is set, the request includes:
```
Authorization: Bearer <REPORT_AUTH value>
```

The server must respond with a plain integer (e.g. `3`). The firmware stores it in the global `server_command` and derives the state flags from its bits.

---

## Server Command Bit Flags

The integer returned by the server is interpreted as a bitmask:

| Bit | Mask | Global variable | Meaning |
|-----|------|----------------|---------|
| 0 (LSB) | `0x01` | `server_competition_ready` | Competition is prepared and ready to start |
| 1 | `0x02` | `server_competition_running` | Competition is actively running |

Additional global variables updated on every request:

| Variable | Type | Description |
|----------|------|-------------|
| `server_command` | `int` | Raw integer value last received from the server |
| `server_online` | `bool` | `True` after a successful POST; `False` after any network error |
| `server_competition_ready` | `bool` | `True` when bit 0 of `server_command` is set |
| `server_competition_running` | `bool` | `True` when bit 1 of `server_command` is set |

**Example server responses:**

| Response | `server_competition_ready` | `server_competition_running` |
|----------|---------------------------|------------------------------|
| `0` | False | False |
| `1` | True | False |
| `2` | False | True |
| `3` | True | True |
