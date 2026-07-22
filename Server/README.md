# PicoBot Fleet Dashboard Server

A **Flask** web application that acts as the remote endpoint for PicoBot status
reports and provides a browser-based dashboard for monitoring and commanding a
fleet of robots.

---

## Table of Contents

1. [Overview](#overview)
2. [Requirements](#requirements)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Running the Server](#running-the-server)
6. [Production Deployment](#production-deployment)
7. [Web Interface](#web-interface)
8. [Managing Competitions](#managing-competitions)
9. [REST API](#rest-api)
10. [Database Schema](#database-schema)
11. [Server Command Bit Flags](#server-command-bit-flags)
12. [Docker Deployment](#docker-deployment)

---

## Overview

Each PicoBot robot periodically sends an HTTPS POST request containing its
current state (MAC address, servo positions, uptime). This server:

- Receives and stores every report in a **SQLite** database.
- Identifies each robot by its **Wi-Fi MAC address**.
- Returns a single integer (`server_command`) to the robot on every request.
  The robot interprets individual bits of this integer as competition-state
  flags (ready, running).
- Provides a **fleet dashboard** listing all known robots with their last-seen
  time and status.
- Provides a **per-robot detail page** showing the full request history.
- Provides a **competition management page** for creating, starting, and
  stopping timed competitions. The active competition state is broadcast
  automatically to all robots.

---

## Requirements

- Python 3.9 or newer
- Flask 3.0 or newer

All Python dependencies are listed in `requirements.txt`.

---

## Installation

```bash
# 1. Clone the repository (if you haven't already)
git clone https://github.com/robosteamdev/picobot-web-control.git
cd picobot-web-control/Server

# 2. Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

The SQLite database file (`picobot.db`) is created automatically in the current
working directory on first run — no separate database setup is needed.

---

## Configuration

All settings live in **`config.py`**. Edit this file before starting the server.

```python
# config.py

HOST = '0.0.0.0'                    # Interface to bind ('127.0.0.1' for local-only)
PORT = 5000                          # TCP port

DATABASE = 'picobot.db'             # Path to the SQLite database file

STATUS_ENDPOINT = '/picobot/status' # POST endpoint path — must match robot REPORT_URL

REPORT_AUTH = None                  # Bearer token; None = no authentication

DEFAULT_COMMAND = 0                 # server_command sent to newly seen robots
```

### Variable Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `'0.0.0.0'` | Network interface to listen on. Use `'127.0.0.1'` to restrict to localhost (e.g. behind a reverse proxy). |
| `PORT` | `5000` | TCP port the Flask development server binds to. |
| `DATABASE` | `'picobot.db'` | Path to the SQLite database file, relative to the working directory. |
| `STATUS_ENDPOINT` | `'/picobot/status'` | URL path for robot POST requests. Must match the path component of `REPORT_URL` in `picobot_config.py` on each robot. |
| `REPORT_AUTH` | `None` | If set, the server rejects any POST whose `Authorization` header does not match `Bearer <value>`. Must match `REPORT_AUTH` in `picobot_config.py` on each robot. |
| `DEFAULT_COMMAND` | `0` | The `server_command` integer returned to a robot the first time it is seen. |

### Matching robot configuration

The robot's `PicoBot/picobot_config.py` must match the server settings:

| Robot setting | Must match server setting |
|---------------|--------------------------|
| `REPORT_URL` | scheme + host + `STATUS_ENDPOINT` |
| `REPORT_AUTH` | `REPORT_AUTH` |

Example pair:

```python
# Robot: PicoBot/picobot_config.py
REPORT_URL  = 'https://myserver.example.com/picobot/status'
REPORT_AUTH = 'secret-token-123'

# Server: Server/config.py
STATUS_ENDPOINT = '/picobot/status'
REPORT_AUTH     = 'secret-token-123'
```

---

## Running the Server

### Development

```bash
cd Server
python app.py
```

The server starts on `http://0.0.0.0:5000`.  
Open `http://localhost:5000` in a browser to view the dashboard.

### Specifying host / port without editing config.py

```bash
python -c "
import config, app
config.HOST = '127.0.0.1'
config.PORT = 8080
app.init_db()
app.app.run(host=config.HOST, port=config.PORT)
"
```

---

## Production Deployment

For production, run the app behind **gunicorn** and an HTTPS-terminating reverse
proxy (nginx, Caddy, etc.). Robots communicate over HTTPS; the Flask app itself
can run plain HTTP on a private port.

### gunicorn

```bash
pip install gunicorn
gunicorn -w 2 -b 127.0.0.1:5000 'app:app'
```

### nginx (HTTPS termination example)

```nginx
server {
    listen 443 ssl;
    server_name myserver.example.com;

    ssl_certificate     /etc/letsencrypt/live/myserver.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/myserver.example.com/privkey.pem;

    location / {
        proxy_pass         http://127.0.0.1:5000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
    }
}
```

### systemd service

```ini
# /etc/systemd/system/picobot-server.service
[Unit]
Description=PicoBot Fleet Server
After=network.target

[Service]
WorkingDirectory=/opt/picobot-web-control/Server
ExecStart=/opt/picobot-web-control/Server/.venv/bin/gunicorn -w 2 -b 127.0.0.1:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now picobot-server
```

---

## Docker Deployment

A `Dockerfile` and `docker-compose.yaml` are provided for containerised deployment.

### Quick start

```bash
docker compose up -d
```

The server starts on port **5000** by default (configurable via `SERVER_PORT`).

### Configuration via environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVER_PORT` | `5000` | Host port mapped to the container's port 5000 |
| `DATABASE` | `/app/data/picobot.db` | Path inside the container; the `db-data` volume keeps it persistent across restarts |
| `REPORT_AUTH` | *(empty)* | Bearer token for robot POST requests (set on both robot and server) |

Example with a custom auth token and alternate port:

```bash
export REPORT_AUTH='secret-token-123'
export SERVER_PORT=8080
docker compose up -d
```

### Dockerfile

The image is built from `python:3.12-slim`, installs dependencies from
`requirements.txt`, and copies the application code. It exposes port 5000 and
runs `python app.py` as the default command.

### Volume persistence

The `db-data` named volume in `docker-compose.yaml` mounts to `/app/data` inside
the container. With `DATABASE=/app/data/picobot.db`, the SQLite database
survives container rebuilds and restarts.

```bash
# Recreate the image without losing data
docker compose up -d --build
```

---

## Web Interface

### Fleet Dashboard — `GET /`

Lists every robot that has ever reported in, ordered by most-recently-seen
first.

| Column | Description |
|--------|-------------|
| **MAC Address** | Wi-Fi adapter MAC (link to per-robot detail page) |
| **First Seen** | UTC timestamp of the robot's very first request |
| **Last Seen** | UTC timestamp of the most recent request |
| **Requests** | Total number of POST requests received from this robot |
| **Servo Base / Arm / Claw** | Last reported servo angles in degrees |
| **Uptime (ms)** | `ticks_ms()` value from the robot at last report |
| **State** | Badges derived from current `command` bits: *Idle*, *Ready*, *Running* |
| **Command** | Number input + **Set** button to update `server_command` for this robot |

### Robot Detail Page — `GET /robot/<mac>`

Shows a summary of the robot's current state (servo positions, command value)
and a full table of **every individual request** received from that robot,
newest first.

| Column | Description |
|--------|-------------|
| **#** | Auto-increment request ID |
| **Received (UTC)** | Timestamp when the server received the request |
| **Servo Base / Arm / Claw** | Servo angles at the time of the request |
| **Uptime (ms)** | Robot uptime at the time of the request |

A **← Back to dashboard** link returns to the fleet view.

### Competition Page — `GET /competition`

Lets operators create, start, and stop competitions. See
[Managing Competitions](#managing-competitions) for the full workflow.

---

## Managing Competitions

The competition system broadcasts a global state to every robot via the
`server_command` bitmask. Only **one competition can be active at a time**.

### Competition states

| State | `competition_ready` | `competition_running` | Description |
|-------|---------------------|-----------------------|-------------|
| No active competition | `False` | `False` | Robots receive `DEFAULT_COMMAND` |
| **Ready** | `True` | `False` | Competition created, waiting to start |
| **Running** | `True` | `True` | Competition in progress; elapsed timer shown |
| **Ended** | — | — | Archived to the past competitions table |

### Step-by-step workflow

1. **Open** `http://<server>/competition` in a browser.

2. **Create** a competition — enter a name in the *Create Competition* form and
   press **Create**. All robots immediately start receiving
   `competition_ready = True`.

3. **Start** the competition — press **▶ Start Competition**. All robots now
   receive `competition_ready = True` and `competition_running = True`. A
   live elapsed-time counter is shown in the browser.

4. **Stop** the competition — press **⏹ Stop Competition** (confirm the
   dialog). The competition is archived. Robots revert to `DEFAULT_COMMAND`
   (idle) until a new competition is created.

> **Cancel before starting:** While in *Ready* state you can press
> **✕ Cancel** to discard the competition without starting it.

### Past competitions

Ended competitions are listed in the *Past Competitions* table on the same
page, showing name, creation/start/end times, and calculated duration.

---

## REST API

### `POST <STATUS_ENDPOINT>`

Receive a status report from a robot and return its `server_command`.

**Headers**

| Header | Required | Value |
|--------|----------|-------|
| `Content-Type` | Yes | `application/json` |
| `Authorization` | If `REPORT_AUTH` is set | `Bearer <token>` |

**Request body**

```json
{
    "mac":        "aa:bb:cc:dd:ee:ff",
    "servo_base": 90,
    "servo_arm":  90,
    "servo_claw": 90,
    "uptime_ms":  12345
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mac` | string | **Yes** | Wi-Fi adapter MAC address — primary key identifying the robot |
| `servo_base` | integer | No | Current base servo angle (degrees) |
| `servo_arm` | integer | No | Current arm servo angle (degrees) |
| `servo_claw` | integer | No | Current claw servo angle (degrees) |
| `uptime_ms` | integer | No | Milliseconds since boot |

**Response**

| Status | Body | Meaning |
|--------|------|---------|
| `200 OK` | Plain integer, e.g. `3` | `server_command` for this robot |
| `400 Bad Request` | Error message | Missing or invalid JSON / missing `mac` field |
| `401 Unauthorized` | `Unauthorized` | Authorization token missing or incorrect |

---

### `POST /robot/<mac>/command`

Update the `server_command` integer for a specific robot (submitted by the
dashboard form; not intended for direct robot use).

**Form field**

| Field | Type | Description |
|-------|------|-------------|
| `command` | integer (0–255) | New `server_command` value |

**Response:** `302` redirect to `/`.

---

### `POST /competition/create`

Create a new competition (browser form submission).

**Form field**

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Display name for the competition (required, non-empty) |

**Response:** `302` redirect to `/competition`.

---

### `POST /competition/<id>/start`

Start a competition that is in *Ready* state. No-op if already started or ended.

**Response:** `302` redirect to `/competition`.

---

### `POST /competition/<id>/stop`

Stop a running or ready competition, archiving it as ended.

**Response:** `302` redirect to `/competition`.

---

## Database Schema

```sql
-- One row per unique robot (keyed by MAC address)
CREATE TABLE robots (
    mac           TEXT PRIMARY KEY,  -- "aa:bb:cc:dd:ee:ff"
    first_seen    TEXT NOT NULL,     -- ISO-8601 UTC, e.g. "2024-01-15T10:30:00+00:00"
    last_seen     TEXT NOT NULL,     -- ISO-8601 UTC
    request_count INTEGER NOT NULL DEFAULT 0,
    servo_base    INTEGER,           -- degrees, last reported value
    servo_arm     INTEGER,           -- degrees, last reported value
    servo_claw    INTEGER,           -- degrees, last reported value
    uptime_ms     INTEGER,           -- last reported uptime
    command       INTEGER NOT NULL DEFAULT 0  -- server_command bitmask
);

-- One row per individual POST request (full history)
CREATE TABLE requests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    mac         TEXT NOT NULL,       -- references robots.mac
    received_at TEXT NOT NULL,       -- ISO-8601 UTC timestamp
    servo_base  INTEGER,
    servo_arm   INTEGER,
    servo_claw  INTEGER,
    uptime_ms   INTEGER,
    FOREIGN KEY (mac) REFERENCES robots(mac)
);

-- One row per competition
CREATE TABLE competitions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,       -- display name
    created_at TEXT NOT NULL,       -- ISO-8601 UTC
    started_at TEXT,                -- ISO-8601 UTC; NULL = not yet started (Ready state)
    ended_at   TEXT                 -- ISO-8601 UTC; NULL = still active
);
```

The active competition is the most-recent row where `ended_at IS NULL`.
The database file is created automatically by `init_db()` (called at startup)
if it does not already exist.

---

## Server Command Bit Flags

The `command` integer stored per robot is a bitmask. The robot reads it on
every POST response and derives:

| Bit | Mask | Robot global | Meaning |
|-----|------|-------------|---------|
| 0 (LSB) | `0x01` | `server_competition_ready` | Competition is prepared and ready to start |
| 1 | `0x02` | `server_competition_running` | Competition is actively running |

**Common values to set in the dashboard:**

| Value | `competition_ready` | `competition_running` | Effect |
|-------|--------------------|-----------------------|--------|
| `0` | False | False | Robot in idle state; controls locked if `SERVER_BRAKE = True` |
| `1` | True | False | Competition ready but not yet started |
| `2` | False | True | Competition running; robot controls unlocked |
| `3` | True | True | Ready and running |
