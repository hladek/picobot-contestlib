"""
PicoBot Fleet Server
====================
Flask application that receives HTTPS POST status reports from PicoBot robots,
stores them in a SQLite database, and shows a live dashboard.

Each robot is identified by its MAC address.  The server returns a single
integer (server_command bitmask) that the robot interprets as:
  bit 0 (0x01) — competition_ready
  bit 1 (0x02) — competition_running
"""

import sqlite3
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, g, jsonify, redirect, render_template_string, request, url_for

import config

app = Flask(__name__)
app.config.from_object(config)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(app.config['DATABASE'])
    db.execute("""
        CREATE TABLE IF NOT EXISTS robots (
            mac             TEXT PRIMARY KEY,
            first_seen      TEXT NOT NULL,
            last_seen       TEXT NOT NULL,
            request_count   INTEGER NOT NULL DEFAULT 0,
            servo_base      INTEGER,
            servo_arm       INTEGER,
            servo_claw      INTEGER,
            uptime_ms       INTEGER,
            command         INTEGER NOT NULL DEFAULT 0
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            mac         TEXT NOT NULL,
            received_at TEXT NOT NULL,
            servo_base  INTEGER,
            servo_arm   INTEGER,
            servo_claw  INTEGER,
            uptime_ms   INTEGER,
            FOREIGN KEY (mac) REFERENCES robots(mac)
        )
    """)
    db.commit()
    db.close()


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

def require_auth(f):
    """Decorator: verify Bearer token when REPORT_AUTH is configured."""
    @wraps(f)
    def decorated(*args, **kwargs):
        expected = app.config.get('REPORT_AUTH')
        if expected is not None:
            auth_header = request.headers.get('Authorization', '')
            if auth_header != f'Bearer {expected}':
                return 'Unauthorized', 401
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route(config.STATUS_ENDPOINT, methods=['POST'])
@require_auth
def receive_status():
    """
    Accept a JSON status report from a robot and return its server_command.

    Expected JSON body:
        {
            "mac":        "aa:bb:cc:dd:ee:ff",
            "servo_base": 90,
            "servo_arm":  90,
            "servo_claw": 90,
            "uptime_ms":  12345
        }

    Response: plain integer text, e.g. "3"
    """
    data = request.get_json(silent=True)
    if not data or 'mac' not in data:
        return 'Bad Request: missing mac field', 400

    mac        = str(data['mac']).lower().strip()
    now        = datetime.now(timezone.utc).isoformat()
    servo_base = data.get('servo_base')
    servo_arm  = data.get('servo_arm')
    servo_claw = data.get('servo_claw')
    uptime_ms  = data.get('uptime_ms')

    db = get_db()

    existing = db.execute('SELECT command FROM robots WHERE mac = ?', (mac,)).fetchone()

    if existing is None:
        db.execute(
            """INSERT INTO robots
               (mac, first_seen, last_seen, request_count,
                servo_base, servo_arm, servo_claw, uptime_ms, command)
               VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)""",
            (mac, now, now, servo_base, servo_arm, servo_claw, uptime_ms,
             app.config['DEFAULT_COMMAND']),
        )
        command = app.config['DEFAULT_COMMAND']
    else:
        db.execute(
            """UPDATE robots SET
               last_seen     = ?,
               request_count = request_count + 1,
               servo_base    = ?,
               servo_arm     = ?,
               servo_claw    = ?,
               uptime_ms     = ?
               WHERE mac = ?""",
            (now, servo_base, servo_arm, servo_claw, uptime_ms, mac),
        )
        command = existing['command']

    db.commit()

    # Record individual request in history
    db.execute(
        """INSERT INTO requests (mac, received_at, servo_base, servo_arm, servo_claw, uptime_ms)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (mac, now, servo_base, servo_arm, servo_claw, uptime_ms),
    )
    db.commit()
    return str(command), 200


@app.route('/robot/<mac>')
def robot_detail(mac):
    """Show all recorded requests from a single robot."""
    db = get_db()
    robot = db.execute('SELECT * FROM robots WHERE mac = ?', (mac,)).fetchone()
    if robot is None:
        return f'Robot {mac} not found', 404
    rows = db.execute(
        'SELECT * FROM requests WHERE mac = ? ORDER BY received_at DESC',
        (mac,),
    ).fetchall()
    return render_template_string(DETAIL_HTML, robot=robot, rows=rows)


@app.route('/robot/<mac>/command', methods=['POST'])
def set_command(mac):
    """Set the server_command integer for a specific robot (submitted from the dashboard)."""
    command = request.form.get('command', type=int, default=0)
    db = get_db()
    db.execute('UPDATE robots SET command = ? WHERE mac = ?', (command, mac))
    db.commit()
    return redirect(url_for('dashboard'))


@app.route('/')
def dashboard():
    db = get_db()
    robots = db.execute(
        'SELECT * FROM robots ORDER BY last_seen DESC'
    ).fetchall()
    return render_template_string(DASHBOARD_HTML, robots=robots)


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PicoBot Fleet Dashboard</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: Arial, sans-serif;
    background: #f0f2f5;
    padding: 24px;
    color: #222;
}
h1 {
    font-size: 1.8em;
    margin-bottom: 20px;
}
table {
    width: 100%;
    border-collapse: collapse;
    background: #fff;
    border-radius: 10px;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}
thead { background: #343a40; color: #fff; }
th, td {
    padding: 12px 16px;
    text-align: left;
    border-bottom: 1px solid #e9ecef;
    vertical-align: middle;
}
tbody tr:last-child td { border-bottom: none; }
tbody tr:hover { background: #f8f9fa; }
.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.82em;
    font-weight: bold;
}
.badge-ready   { background: #d4edda; color: #155724; }
.badge-running { background: #cce5ff; color: #004085; }
.badge-off     { background: #e2e3e5; color: #383d41; }
.cmd-form { display: flex; gap: 6px; align-items: center; }
.cmd-form input[type=number] {
    width: 70px;
    padding: 4px 8px;
    border: 1px solid #ced4da;
    border-radius: 6px;
    font-size: 0.95em;
}
.cmd-form button {
    padding: 4px 12px;
    background: #007bff;
    color: #fff;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.95em;
}
.cmd-form button:hover { background: #0056b3; }
.no-robots { padding: 32px; text-align: center; color: #6c757d; font-size: 1.1em; }
</style>
</head>
<body>
<h1>🤖 PicoBot Fleet Dashboard</h1>
{% if robots %}
<table>
  <thead>
    <tr>
      <th>MAC Address</th>
      <th>First Seen (UTC)</th>
      <th>Last Seen (UTC)</th>
      <th>Requests</th>
      <th>Servo Base</th>
      <th>Servo Arm</th>
      <th>Servo Claw</th>
      <th>Uptime (ms)</th>
      <th>State</th>
      <th>Command</th>
    </tr>
  </thead>
  <tbody>
  {% for r in robots %}
    <tr>
      <td><a href="/robot/{{ r.mac }}"><code>{{ r.mac }}</code></a></td>
      <td>{{ r.first_seen[:19].replace('T',' ') }}</td>
      <td>{{ r.last_seen[:19].replace('T',' ') }}</td>
      <td>{{ r.request_count }}</td>
      <td>{{ r.servo_base }}°</td>
      <td>{{ r.servo_arm }}°</td>
      <td>{{ r.servo_claw }}°</td>
      <td>{{ r.uptime_ms }}</td>
      <td>
        {% set cmd = r.command %}
        {% if cmd & 2 %}
          <span class="badge badge-running">Running</span>
        {% endif %}
        {% if cmd & 1 %}
          <span class="badge badge-ready">Ready</span>
        {% endif %}
        {% if not (cmd & 3) %}
          <span class="badge badge-off">Idle</span>
        {% endif %}
      </td>
      <td>
        <form class="cmd-form" method="post"
              action="/robot/{{ r.mac }}/command">
          <input type="number" name="command" min="0" max="255"
                 value="{{ r.command }}">
          <button type="submit">Set</button>
        </form>
      </td>
    </tr>
  {% endfor %}
  </tbody>
</table>
{% else %}
  <div class="no-robots">No robots have reported in yet.</div>
{% endif %}
</body>
</html>"""


DETAIL_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PicoBot {{ robot.mac }}</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: Arial, sans-serif;
    background: #f0f2f5;
    padding: 24px;
    color: #222;
}
h1 { font-size: 1.6em; margin-bottom: 6px; }
.sub { color: #6c757d; margin-bottom: 20px; font-size: 0.95em; }
.back { display: inline-block; margin-bottom: 20px; color: #007bff; text-decoration: none; font-size: 0.95em; }
.back:hover { text-decoration: underline; }
.summary {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    margin-bottom: 24px;
}
.card {
    background: #fff;
    border-radius: 10px;
    padding: 14px 20px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.08);
    min-width: 140px;
}
.card .label { font-size: 0.78em; color: #6c757d; text-transform: uppercase; letter-spacing: 0.05em; }
.card .value { font-size: 1.4em; font-weight: bold; margin-top: 2px; }
table {
    width: 100%;
    border-collapse: collapse;
    background: #fff;
    border-radius: 10px;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}
thead { background: #343a40; color: #fff; }
th, td {
    padding: 10px 16px;
    text-align: left;
    border-bottom: 1px solid #e9ecef;
}
tbody tr:last-child td { border-bottom: none; }
tbody tr:hover { background: #f8f9fa; }
.empty { padding: 32px; text-align: center; color: #6c757d; }
</style>
</head>
<body>
<a class="back" href="/">← Back to dashboard</a>
<h1>🤖 {{ robot.mac }}</h1>
<p class="sub">First seen: {{ robot.first_seen[:19].replace('T',' ') }} UTC &nbsp;|&nbsp;
               Total requests: {{ robot.request_count }}</p>

<div class="summary">
  <div class="card">
    <div class="label">Servo Base</div>
    <div class="value">{{ robot.servo_base }}°</div>
  </div>
  <div class="card">
    <div class="label">Servo Arm</div>
    <div class="value">{{ robot.servo_arm }}°</div>
  </div>
  <div class="card">
    <div class="label">Servo Claw</div>
    <div class="value">{{ robot.servo_claw }}°</div>
  </div>
  <div class="card">
    <div class="label">Uptime (ms)</div>
    <div class="value">{{ robot.uptime_ms }}</div>
  </div>
  <div class="card">
    <div class="label">Command</div>
    <div class="value">{{ robot.command }}</div>
  </div>
</div>

{% if rows %}
<table>
  <thead>
    <tr>
      <th>#</th>
      <th>Received (UTC)</th>
      <th>Servo Base</th>
      <th>Servo Arm</th>
      <th>Servo Claw</th>
      <th>Uptime (ms)</th>
    </tr>
  </thead>
  <tbody>
  {% for row in rows %}
    <tr>
      <td>{{ row.id }}</td>
      <td>{{ row.received_at[:19].replace('T',' ') }}</td>
      <td>{{ row.servo_base }}°</td>
      <td>{{ row.servo_arm }}°</td>
      <td>{{ row.servo_claw }}°</td>
      <td>{{ row.uptime_ms }}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>
{% else %}
  <div class="empty">No requests recorded yet.</div>
{% endif %}
</body>
</html>"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    init_db()
    app.run(
        host=app.config['HOST'],
        port=app.config['PORT'],
        debug=False,
    )
