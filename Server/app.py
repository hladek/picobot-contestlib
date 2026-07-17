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


@app.template_filter('bitand')
def bitand_filter(value, mask):
    return int(value) & int(mask)


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
            ip              TEXT,
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
    db.execute("""
        CREATE TABLE IF NOT EXISTS competitions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            created_at TEXT NOT NULL,
            started_at TEXT,
            ended_at   TEXT
        )
    """)
    db.commit()
    db.close()


def migrate_db():
    """Apply incremental schema migrations to an existing database."""
    db = sqlite3.connect(app.config['DATABASE'])
    existing = {row[1] for row in db.execute("PRAGMA table_info(robots)")}
    if 'ip' not in existing:
        db.execute("ALTER TABLE robots ADD COLUMN ip TEXT")
    db.commit()
    db.close()


# ---------------------------------------------------------------------------
# Competition helpers
# ---------------------------------------------------------------------------

def get_active_competition(db):
    """Return the active competition row (ready or running), or None."""
    return db.execute(
        "SELECT * FROM competitions WHERE ended_at IS NULL ORDER BY created_at DESC LIMIT 1"
    ).fetchone()


def get_competition_command(db):
    """
    Derive server_command from the current competition state:
      no active competition → DEFAULT_COMMAND
      competition ready (not started) → 0x01
      competition running (started, not ended) → 0x03
    """
    comp = get_active_competition(db)
    if comp is None:
        return app.config['DEFAULT_COMMAND']
    if comp['started_at'] is None:
        return 0x01  # competition_ready
    return 0x03      # competition_ready + competition_running


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
            "ip":         "192.168.4.1",
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
    ip         = str(data['ip']).strip() if data.get('ip') else None
    servo_base = data.get('servo_base')
    servo_arm  = data.get('servo_arm')
    servo_claw = data.get('servo_claw')
    uptime_ms  = data.get('uptime_ms')

    db = get_db()

    db.execute(
        """INSERT INTO robots
               (mac, first_seen, last_seen, request_count,
                ip, servo_base, servo_arm, servo_claw, uptime_ms, command)
               VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(mac) DO UPDATE SET
               last_seen     = excluded.last_seen,
               request_count = request_count + 1,
               ip            = excluded.ip,
               servo_base    = excluded.servo_base,
               servo_arm     = excluded.servo_arm,
               servo_claw    = excluded.servo_claw,
               uptime_ms     = excluded.uptime_ms""",
        (mac, now, now, ip, servo_base, servo_arm, servo_claw, uptime_ms,
         app.config['DEFAULT_COMMAND']),
    )

    command = get_competition_command(db)

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


@app.route('/competition')
def competition_view():
    db = get_db()
    active = get_active_competition(db)
    past = db.execute(
        'SELECT * FROM competitions WHERE ended_at IS NOT NULL ORDER BY ended_at DESC'
    ).fetchall()

    def duration(row):
        if not row['started_at'] or not row['ended_at']:
            return '—'
        try:
            s = datetime.fromisoformat(row['started_at'])
            e = datetime.fromisoformat(row['ended_at'])
            secs = int((e - s).total_seconds())
            h, rem = divmod(secs, 3600)
            m, s = divmod(rem, 60)
            return f'{h:02d}:{m:02d}:{s:02d}'
        except Exception:
            return '—'

    return render_template_string(COMPETITION_HTML, active=active, past=past, duration=duration)


@app.route('/competition/create', methods=['POST'])
def competition_create():
    name = request.form.get('name', '').strip()
    if not name:
        return redirect(url_for('competition_view'))
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    db.execute('INSERT INTO competitions (name, created_at) VALUES (?, ?)', (name, now))
    db.commit()
    return redirect(url_for('competition_view'))


@app.route('/competition/<int:comp_id>/start', methods=['POST'])
def competition_start(comp_id):
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        'UPDATE competitions SET started_at = ? WHERE id = ? AND started_at IS NULL AND ended_at IS NULL',
        (now, comp_id),
    )
    db.commit()
    return redirect(url_for('competition_view'))


@app.route('/competition/<int:comp_id>/stop', methods=['POST'])
def competition_stop(comp_id):
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        'UPDATE competitions SET ended_at = ? WHERE id = ? AND started_at IS NOT NULL AND ended_at IS NULL',
        (now, comp_id),
    )
    db.commit()
    return redirect(url_for('competition_view'))


@app.route('/')
def dashboard():
    db = get_db()
    robots = db.execute(
        'SELECT * FROM robots ORDER BY last_seen DESC'
    ).fetchall()
    active = get_active_competition(db)
    return render_template_string(DASHBOARD_HTML, robots=robots, active=active)


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Shared HTML fragments (Bootstrap 5)
# ---------------------------------------------------------------------------

_BS_HEAD = """\
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
  body { background: #f0f2f5; }
  .table thead { background: #343a40; color: #fff; }
  .timer { font-size: 3rem; font-variant-numeric: tabular-nums; font-weight: 700; letter-spacing: .05em; }
  .stat-label { font-size: .75rem; text-transform: uppercase; letter-spacing: .06em; color: #6c757d; }
  .stat-value { font-size: 1.5rem; font-weight: 700; }
</style>"""

def _nav(active):
    """Render a Bootstrap navbar. active: 'dashboard' | 'competition'"""
    def _li(label, href, key):
        cls = 'nav-link active fw-semibold' if active == key else 'nav-link'
        return f'<li class="nav-item"><a class="{cls}" href="{href}">{label}</a></li>'
    return (
        '<nav class="navbar navbar-expand navbar-dark bg-dark px-3 mb-4">'
        '<a class="navbar-brand me-4" href="/">🤖 PicoBot</a>'
        '<ul class="navbar-nav">'
        + _li('Dashboard', '/', 'dashboard')
        + _li('Competition', '/competition', 'competition')
        + '</ul></nav>'
    )

NAV_DASHBOARD   = _nav('dashboard')
NAV_COMPETITION = _nav('competition')
NAV_DETAIL      = _nav(None)

# ---------------------------------------------------------------------------
# Dashboard template
# ---------------------------------------------------------------------------

DASHBOARD_HTML = (
"""<!DOCTYPE html>
<html lang="en">
<head>""" + _BS_HEAD + """
<title>PicoBot Dashboard</title>
</head>
<body>
""" + NAV_DASHBOARD + """
<div class="container-fluid px-4">
  <h4 class="mb-3">Fleet Dashboard</h4>

  {% if active %}
    {% if active.started_at %}
      <div class="alert alert-primary d-flex align-items-center gap-2 py-2" role="alert">
        <span class="badge bg-primary">🏁 Running</span>
        Competition: <strong>{{ active.name }}</strong>
        — robots receive <code>competition_running = True</code>
      </div>
    {% else %}
      <div class="alert alert-success d-flex align-items-center gap-2 py-2" role="alert">
        <span class="badge bg-success">✅ Ready</span>
        Competition: <strong>{{ active.name }}</strong>
        — robots receive <code>competition_ready = True</code>
      </div>
    {% endif %}
  {% endif %}

  {% if robots %}
  <div class="card shadow-sm">
    <div class="card-body p-0">
      <table class="table table-hover table-bordered mb-0 align-middle">
        <thead>
          <tr>
            <th>MAC / IP</th>
            <th>First Seen (UTC)</th>
            <th>Last Seen (UTC)</th>
            <th>Requests</th>
            <th>Base</th><th>Arm</th><th>Claw</th>
            <th>Uptime (ms)</th>
            <th>State</th>
          </tr>
        </thead>
        <tbody>
        {% for r in robots %}
          {% set cmd = r.command %}
          <tr>
            <td><a href="/robot/{{ r.mac }}"><code>{{ r.mac }}</code></a>{% if r.ip %}<br><small class="text-muted">{{ r.ip }}</small>{% endif %}</td>
            <td class="text-nowrap">{{ r.first_seen[:19].replace('T',' ') }}</td>
            <td class="text-nowrap">{{ r.last_seen[:19].replace('T',' ') }}</td>
            <td class="text-center">{{ r.request_count }}</td>
            <td class="text-center">{{ r.servo_base }}°</td>
            <td class="text-center">{{ r.servo_arm }}°</td>
            <td class="text-center">{{ r.servo_claw }}°</td>
            <td class="text-center">{{ r.uptime_ms }}</td>
            <td>
              {% if cmd | bitand(2) %}<span class="badge bg-primary">Running</span>{% endif %}
              {% if cmd | bitand(1) %}<span class="badge bg-success">Ready</span>{% endif %}
              {% if not (cmd | bitand(3)) %}<span class="badge bg-secondary">Idle</span>{% endif %}
            </td>
          </tr>
        {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
  {% else %}
    <div class="text-center text-muted py-5">No robots have reported in yet.</div>
  {% endif %}
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>""")

# ---------------------------------------------------------------------------
# Robot detail template
# ---------------------------------------------------------------------------

DETAIL_HTML = (
"""<!DOCTYPE html>
<html lang="en">
<head>""" + _BS_HEAD + """
<title>PicoBot {{ robot.mac }}</title>
</head>
<body>
""" + NAV_DETAIL + """
<div class="container-fluid px-4">
  <a href="/" class="btn btn-sm btn-outline-secondary mb-3">← Back to Dashboard</a>

  <h4 class="mb-0"><code>{{ robot.mac }}</code>{% if robot.ip %} <small class="text-muted fs-6">{{ robot.ip }}</small>{% endif %}</h4>
  <p class="text-muted small mb-3">
    First seen: {{ robot.first_seen[:19].replace('T',' ') }} UTC
     |  Total requests: <strong>{{ robot.request_count }}</strong>
  </p>

  <div class="row g-3 mb-4">
    {% for label, val in [
        ('Servo Base',  robot.servo_base|string + '°'),
        ('Servo Arm',   robot.servo_arm|string  + '°'),
        ('Servo Claw',  robot.servo_claw|string + '°'),
        ('Uptime ms',   robot.uptime_ms|string),
    ] %}
    <div class="col-6 col-sm-3 col-lg-2">
      <div class="card shadow-sm text-center py-3">
        <div class="stat-label">{{ label }}</div>
        <div class="stat-value">{{ val }}</div>
      </div>
    </div>
    {% endfor %}
  </div>

  <h5 class="mb-3">Request History</h5>
  {% if rows %}
  <div class="card shadow-sm">
    <div class="card-body p-0">
      <table class="table table-hover table-bordered mb-0 align-middle">
        <thead>
          <tr>
            <th>#</th>
            <th>Received (UTC)</th>
            <th>Servo Base</th><th>Servo Arm</th><th>Servo Claw</th>
            <th>Uptime (ms)</th>
          </tr>
        </thead>
        <tbody>
        {% for row in rows %}
          <tr>
            <td>{{ row.id }}</td>
            <td class="text-nowrap">{{ row.received_at[:19].replace('T',' ') }}</td>
            <td class="text-center">{{ row.servo_base }}°</td>
            <td class="text-center">{{ row.servo_arm }}°</td>
            <td class="text-center">{{ row.servo_claw }}°</td>
            <td class="text-center">{{ row.uptime_ms }}</td>
          </tr>
        {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
  {% else %}
    <div class="text-center text-muted py-5">No requests recorded yet.</div>
  {% endif %}
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>""")

# ---------------------------------------------------------------------------
# Competition template
# ---------------------------------------------------------------------------

COMPETITION_HTML = (
"""<!DOCTYPE html>
<html lang="en">
<head>""" + _BS_HEAD + """
<title>PicoBot Competition</title>
</head>
<body>
""" + NAV_COMPETITION + """
<div class="container-fluid px-4">
  <h4 class="mb-4">Competition</h4>

  {# ── Active competition panel ── #}
  {% if active %}

    {% if active.started_at is none %}
    {# READY #}
    <div class="card shadow-sm mb-4" style="max-width:560px">
      <div class="card-body">
        <h5 class="card-title d-flex align-items-center gap-2">
          {{ active.name }}
          <span class="badge bg-success">✅ Ready</span>
        </h5>
        <p class="text-muted mb-3">
          Competition is set up. Robots are receiving
          <code>competition_ready = True</code>.
        </p>
        <div class="d-flex gap-2">
          <form method="post" action="/competition/{{ active.id }}/start">
            <button class="btn btn-success" type="submit">▶ Start Competition</button>
          </form>
          <form method="post" action="/competition/{{ active.id }}/stop"
                onsubmit="return confirm('Cancel this competition?')">
            <button class="btn btn-outline-danger" type="submit">✕ Cancel</button>
          </form>
        </div>
      </div>
    </div>

    {% else %}
    {# RUNNING #}
    <div class="card shadow-sm mb-4 border-primary" style="max-width:560px">
      <div class="card-body">
        <h5 class="card-title d-flex align-items-center gap-2">
          {{ active.name }}
          <span class="badge bg-primary">🏁 Running</span>
        </h5>
        <div class="timer text-primary my-3" id="timer">00:00:00</div>
        <p class="text-muted mb-3">
          Robots are receiving <code>competition_ready = True</code>
          and <code>competition_running = True</code>.
        </p>
        <form method="post" action="/competition/{{ active.id }}/stop"
              onsubmit="return confirm('Stop the competition?')">
          <button class="btn btn-danger" type="submit">⏹ Stop Competition</button>
        </form>
      </div>
    </div>
    <script>
      const startedAt = new Date("{{ active.started_at }}");
      function updateTimer() {
        const elapsed = Math.max(0, Math.floor((Date.now() - startedAt) / 1000));
        const h = Math.floor(elapsed / 3600);
        const m = Math.floor((elapsed % 3600) / 60);
        const s = elapsed % 60;
        document.getElementById('timer').textContent =
          String(h).padStart(2,'0') + ':' +
          String(m).padStart(2,'0') + ':' +
          String(s).padStart(2,'0');
      }
      setInterval(updateTimer, 1000);
      updateTimer();
    </script>
    {% endif %}

  {% else %}
  {# NO ACTIVE COMPETITION #}
  <div class="card shadow-sm mb-4" style="max-width:560px">
    <div class="card-body">
      <h5 class="card-title">Create Competition</h5>
      <p class="text-muted mb-3">
        Enter a name and press <em>Create</em>. The competition will be set to
        <strong>Ready</strong> and robots will receive
        <code>competition_ready = True</code>.
      </p>
      <form method="post" action="/competition/create">
        <div class="input-group">
          <input type="text" class="form-control" name="name"
                 placeholder="Competition name…" required autofocus>
          <button class="btn btn-primary" type="submit">Create</button>
        </div>
      </form>
    </div>
  </div>
  {% endif %}

  {# ── Past competitions ── #}
  {% if past %}
  <h5 class="mb-3">Past Competitions</h5>
  <div class="card shadow-sm">
    <div class="card-body p-0">
      <table class="table table-hover table-bordered mb-0 align-middle">
        <thead>
          <tr>
            <th>#</th><th>Name</th>
            <th>Created (UTC)</th><th>Started (UTC)</th>
            <th>Ended (UTC)</th><th>Duration</th>
          </tr>
        </thead>
        <tbody>
        {% for c in past %}
          <tr>
            <td>{{ c.id }}</td>
            <td>{{ c.name }}</td>
            <td class="text-nowrap">{{ c.created_at[:19].replace('T',' ') }}</td>
            <td class="text-nowrap">{{ c.started_at[:19].replace('T',' ') if c.started_at else '—' }}</td>
            <td class="text-nowrap">{{ c.ended_at[:19].replace('T',' ') }}</td>
            <td><code>{{ duration(c) }}</code></td>
          </tr>
        {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
  {% endif %}

</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>""")

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    init_db()
    migrate_db()
    app.run(
        host=app.config['HOST'],
        port=app.config['PORT'],
        debug=False,
    )
