# picobot_main.py non-blocking web control v6
#@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

#import sys
#sys.path.append('/PicoBot')

'''
Wih onboard LED ON on Wi-Fi connection
Use https://jsfiddle.net/ to create the WEB page
'''
import network
import socket
from time import sleep
import time
import machine
import ubinascii
import urequests
import ujson
from picobot import PicoBot
from picobot_config import REPORT_URL, REPORT_DELAY, SERVER_ENABLE, SERVER_BRAKE, REPORT_AUTH, WIFI_SSID, WIFI_PASSWORD
import rp2


# Define led object and set LED pin to OUT
led = machine.Pin('LED', machine.Pin.OUT)
led.off()

# Global variable storing the last integer command received from the reporting server
server_command = 0

# True after at least one successful POST to the reporting server
server_online = False

# True when bit 0 of server_command is set
server_competition_ready = False

# True when bit 1 of server_command is set
server_competition_running = False

# Wireless adapter MAC address (resolved once at startup)
wlan_mac = ubinascii.hexlify(network.WLAN(network.STA_IF).config('mac'), ':').decode()

# IP address assigned after Wi-Fi connection (set at startup)
wlan_ip = ''

# Create robot object
robot = PicoBot()

# Set country to avoid possible errors
rp2.country('BG')



def move_left_forward():
    print ("Left Forward")
    robot.moveLeftForward()
    sleep(0.1)  # Small delay
    
def move_forward():
    print ("Forward")
    robot.goForward()
    sleep(0.1)
        
def move_right_forward():
    print ("Right Forward")
    robot.moveRightForward()
    sleep(0.1)
    
def move_left():
    print ("Left")
    robot.moveLeft()
    sleep(0.1)
    
def stop():
    print ("Stop")
    robot.hardStop()
    sleep(0.1)
    
def move_right():
    print ("Right")
    robot.moveRight()
    sleep(0.1)
    
def move_left_backward():
    print ("Left Backward")
    robot.moveLeftBackward()
    sleep(0.1)
    
def move_backward():
    print ("Backward")
    robot.goBackwad()
    sleep(0.1)
    
def move_right_backward():
    print ("Right Backward")
    robot.moveRightBackward()
    sleep(0.1)
    
def rotate_left():
    print ("Rotate Left")
    robot.rotateLeft()
    sleep(0.1)
    
def rotate_right():
    print ("Rotate right")
    robot.rotateRight()
    sleep(0.1)


def connect():
    #Connect to WLAN
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    # If you need to disable powersaving mode
    # wlan.config(pm = 0xa11140)

    # Print the MAC address in the wireless chip OTP
    mac = ubinascii.hexlify(network.WLAN().config('mac'),':').decode()
    print('mac = ' + mac)
    # Other things to query
    # print(wlan.config('channel'))
    # print(wlan.config('essid'))
    # print(wlan.config('txpower'))
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    while wlan.isconnected() == False:
        print('Waiting for connection...')
        sleep(1)
    ip = wlan.ifconfig()[0]
    # Turn onboard LED ON when Wi-Fi is connected
    led.on()
    print(f'Connected on {ip}')
    return ip

def open_socket(ip):
    # Open a socket
    address = (ip, 80)
    connection = socket.socket()
    # from https://forum.micropython.org/viewtopic.php?f=18&t=10412 
    ## Add this line to resolve WiFi issue ???
    connection.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    ##
    connection.bind(address)
    connection.listen(1)
    return connection

def webpage():
    # Touch-friendly HTML for Samsung S22 Ultra
    def _badge(flag):
        return '<span style="color:#28a745;font-weight:bold">YES</span>' if flag else '<span style="color:#dc3545;font-weight:bold">NO</span>'

    controls_locked = SERVER_BRAKE and not server_competition_running
    disabled_attr   = 'disabled' if controls_locked else ''
    overlay_style   = 'display:block' if controls_locked else 'display:none'

    status_bar = ''
    if SERVER_ENABLE:
        status_bar = """<div class="status-bar">
  <span>Server online: {online}</span>
  <span>Competition ready: {ready}</span>
  <span>Competition running: {running}</span>
</div>""".format(
            online=_badge(server_online),
            ready=_badge(server_competition_ready),
            running=_badge(server_competition_running),
        )

    html = """<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>PicoBot Control</title>
<style>
*{{box-sizing:border-box}}
body{{font-family:Arial,sans-serif;text-align:center;background:#f0f2f5;margin:0;padding:6px;touch-action:manipulation}}
h1{{font-size:1.6em;margin:8px 0}}
h3{{font-size:1.1em;margin:8px 0 4px}}
.status-bar{{display:flex;justify-content:center;gap:12px;flex-wrap:wrap;background:#fff;border-radius:8px;padding:5px 12px;margin:5px auto;max-width:600px;font-size:0.95em;box-shadow:0 1px 4px rgba(0,0,0,0.1)}}
.control-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;max-width:480px;margin:0 auto;padding:4px}}
.control-btn{{height:70px;width:100%;font-size:1.1em;background:#007bff;color:#fff;border:none;border-radius:10px;cursor:pointer;touch-action:manipulation;padding:4px}}
.control-btn:active{{background:#0056b3}}
.stop-btn{{background:#dc3545}}
.stop-btn:active{{background:#c82333}}
.arm-grid{{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:4px 8px;max-width:480px;margin:0 auto;padding:6px 10px;background:#fff;border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,0.1)}}
.arm-label{{font-size:1em;font-weight:bold;text-align:right}}
.slider{{width:100%;height:36px;margin:0}}
.slider-value{{font-size:1em;font-weight:bold;min-width:38px;text-align:left}}
.controls-wrap{{position:relative}}
.controls-overlay{{position:absolute;inset:0;background:rgba(200,200,200,0.65);border-radius:10px;z-index:10;display:flex;align-items:center;justify-content:center;font-size:1.3em;font-weight:bold;color:#555;pointer-events:all}}
#reset{{background:#ff5733;height:46px;width:160px;font-size:1.1em;border:none;border-radius:10px;margin:8px auto;cursor:pointer;color:#fff;display:block}}
#reset:active{{background:#c70039}}
@media(max-width:400px){{.control-btn{{height:60px;font-size:1em}}h1{{font-size:1.3em}}}}
</style>
</head>
<body>
<h1>🤖 PicoBot Control</h1>
""" + status_bar + """
<div class="controls-wrap">
<div class="controls-overlay" style="{overlay_style}">🔒 Waiting for competition start</div>

<div class="control-grid">
  <button class="control-btn" onclick="c('left_forward')" {disabled}>↖️ L-Fwd</button>
  <button class="control-btn" onclick="c('forward')" {disabled}>⬆️ Fwd</button>
  <button class="control-btn" onclick="c('right_forward')" {disabled}>↗️ R-Fwd</button>
  <button class="control-btn" onclick="c('left')" {disabled}>⬅️ Left</button>
  <button class="control-btn stop-btn" onclick="c('stop')" {disabled}>⏹️ STOP</button>
  <button class="control-btn" onclick="c('right')" {disabled}>➡️ Right</button>
  <button class="control-btn" onclick="c('left_back')" {disabled}>↙️ L-Back</button>
  <button class="control-btn" onclick="c('back')" {disabled}>⬇️ Back</button>
  <button class="control-btn" onclick="c('right_back')" {disabled}>↘️ R-Back</button>
  <button class="control-btn" onclick="c('rotate_left')" {disabled}>🔄 Rot-L</button>
  <button class="control-btn stop-btn" onclick="c('stop')" {disabled}>⏹️ STOP</button>
  <button class="control-btn" onclick="c('rotate_right')" {disabled}>🔃 Rot-R</button>
</div>

<h3>🦾 Arm Control</h3>
<div class="arm-grid">
  <span class="arm-label">Base</span>
  <input type="range" class="slider" id="base_slider" min="0" max="180" value="90" onchange="s('base',this.value)" {disabled}>
  <span class="slider-value" id="base_value">90°</span>
  <span class="arm-label">Arm</span>
  <input type="range" class="slider" id="arm_slider" min="40" max="140" value="90" onchange="s('arm',this.value)" {disabled}>
  <span class="slider-value" id="arm_value">90°</span>
  <span class="arm-label">Claw</span>
  <input type="range" class="slider" id="claw_slider" min="40" max="140" value="90" onchange="s('claw',this.value)" {disabled}>
  <span class="slider-value" id="claw_value">90°</span>
</div>

<button id="reset" onclick="resetAll()" {disabled}>🔄 Reset All</button>
</div>""".format(overlay_style=overlay_style, disabled=disabled_attr) + """
<script>
function c(action) {
    fetch('./' + action + '?').catch(e => console.log('Error:', e));
}

function s(type, value) {
    document.getElementById(type + '_value').textContent = value + '°';
    fetch('./?servo_' + type + '_slider=' + value).catch(e => console.log('Error:', e));
}

function resetAll() {
    fetch('./reset_to_default?')
        .then(() => {
            // Update all sliders and values to 90° after successful reset
            ['base', 'arm', 'claw'].forEach(type => {
                document.getElementById(type + '_slider').value = 90;
                document.getElementById(type + '_value').textContent = '90°';
            });
            console.log('Reset complete - sliders updated');
        })
        .catch(e => console.log('Reset error:', e));
}

// Initialize slider values on page load
window.onload = function() {
    ['base', 'arm', 'claw'].forEach(type => {
        document.getElementById(type + '_value').textContent = 
            document.getElementById(type + '_slider').value + '°';
    });
};
</script>
</body></html>"""
    return html

def process_request(request):
    """Process the HTTP request without blocking the server"""
    print("Received request:", request)

    # When SERVER_BRAKE is active and competition is not running, ignore all commands
    if SERVER_BRAKE and not server_competition_running:
        print("SERVER_BRAKE: control locked, ignoring command")
        return
    
    # Extract the query string part (after the ?)
    if '?' in request:
        query_string = request.split('?')[1]
        params = query_string.split('&')
        
        # Process each parameter
        for param in params:
            if '=' in param:
                key, value = param.split('=', 1)
                
                # Process servo controls
                if key == 'servo_base_slider':
                    try:
                        slider_angle = int(value)
                        if slider_angle < 0: slider_angle = 0
                        if slider_angle > 180: slider_angle = 180
                        robot.arm.smooth_move_servo(0, slider_angle)
                        print(f"Base slider set to {slider_angle}")
                    except:
                        print("Error processing base slider")
                
                elif key == 'servo_arm_slider':
                    try:
                        slider_angle = int(value)
                        if slider_angle < 40: slider_angle = 40
                        if slider_angle > 140: slider_angle = 140
                        robot.arm.smooth_move_servo(1, slider_angle)
                        print(f"Arm slider set to {slider_angle}")
                    except:
                        print("Error processing arm slider")
                
                elif key == 'servo_claw_slider':
                    try:
                        slider_angle = int(value)
                        if slider_angle < 40: slider_angle = 40
                        if slider_angle > 140: slider_angle = 140
                        robot.arm.smooth_move_servo(2, slider_angle)
                        print(f"Claw slider set to {slider_angle}")
                    except:
                        print("Error processing claw slider")

    # Process movement commands and reset
    if '/reset_to_default?' in request:
        robot.arm.reset_servos()
        print("Reset to default.")
                
    # Process movement commands - these execute immediately
    if '/left_forward?' in request:
        move_left_forward()        
    elif '/forward?' in request:
        move_forward()
    elif '/right_forward?' in request:
        move_right_forward() 
    elif '/left?' in request:
        move_left()
    elif '/stop?' in request:
        stop()
    elif '/right?' in request:
        move_right()
    elif '/left_back?' in request:
        move_left_backward()
    elif '/back?' in request:
        move_backward()
    elif '/right_back?' in request:
        move_right_backward()
    elif '/rotate_left?' in request:
        rotate_left()
    elif '/rotate_right?' in request:
        rotate_right()

def get_board_status():
    """Return a dict with the current board state."""
    return {
        'mac':        wlan_mac,
        'ip':         wlan_ip,
        'servo_base': robot.arm.current_angles.get(0, 90),
        'servo_arm':  robot.arm.current_angles.get(1, 90),
        'servo_claw': robot.arm.current_angles.get(2, 90),
        'uptime_ms':  time.ticks_ms(),
    }

def send_status():
    """POST board status to the reporting server over HTTPS.
    Stores the integer returned by the server in the global server_command.
    Sets server_online to True on success, False on failure."""
    global server_command, server_online, server_competition_ready, server_competition_running
    try:
        status = get_board_status()
        headers = {'Content-Type': 'application/json'}
        if REPORT_AUTH is not None:
            headers['Authorization'] = 'Bearer ' + REPORT_AUTH
        response = urequests.post(
            REPORT_URL,
            headers=headers,
            data=ujson.dumps(status),
        )
        server_command = int(response.text.strip())
        response.close()
        server_online = True
        server_competition_ready   = bool(server_command & 0x01)
        server_competition_running = bool(server_command & 0x02)
        print('server_command:', server_command, 'competition_ready:', server_competition_ready, 'competition_running:', server_competition_running)
    except Exception as e:
        server_online = False
        print('Status report error:', e)


def serve(connection):
    #Start web server with better error handling
    connection.settimeout(1)  # non-blocking accept; allows periodic status sends
    last_report = time.ticks_ms()

    while True:
        # Periodic HTTPS status report
        if SERVER_ENABLE and time.ticks_diff(time.ticks_ms(), last_report) >= REPORT_DELAY * 1000:
            send_status()
            last_report = time.ticks_ms()

        try:
            client, addr = connection.accept()
        except OSError:
            # Timeout on accept — no client yet, loop back to check timer
            continue

        print('Client connected from', addr)
        try:
            request = client.recv(1024)
            request = str(request)
            print('Request:', request)
            
            try:
                request_path = request.split()[1]
            except IndexError:
                request_path = '/'
            
            # Process the request FIRST, then send the HTML response
            process_request(request_path)
            
            # Send HTML response after processing the command
            html = webpage()
            response = 'HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n' + html
            client.send(response)
            
        except Exception as e:
            print('Error handling request:', e)
            try:
                client.send('HTTP/1.0 500 Internal Server Error\r\nContent-type: text/plain\r\n\r\nServer Error')
            except:
                pass
                
        finally:
            try:
                client.close()
            except:
                pass
            print('Client disconnected')


try:
    ip = connect()
    wlan_ip = ip
    connection = open_socket(ip)
    print(f'Reporting status to {REPORT_URL} every {REPORT_DELAY}s')
    serve(connection)
except KeyboardInterrupt:
    machine.reset()