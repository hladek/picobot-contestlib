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
from picobot_config import REPORT_URL, REPORT_DELAY
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
wlan_mac = ubinascii.hexlify(network.WLAN(network.AP_IF).config('mac'), ':').decode()

# Create robot object
robot = PicoBot()

# Set country to avoid possible errors
rp2.country('BG')


##ssid = 'smart_home'
##password = 'Stem123*'
# Load login data from different file for safety reasons
#ssid = secrets['ssid']
#password = secrets['pw']
ssid = 'picobot-web'
password = '12345678'

# Got IP 10.11.12.242

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
    wlan.connect(ssid, password)
    while wlan.isconnected() == False:
        print('Waiting for connection...')
        sleep(1)
    ip = wlan.ifconfig()[0]
    # Turn onboard LED ON when Wi-Fi is connected
    led.on()
    print(f'Connected on {ip}')
    return ip

def create_WiFi_AP():
    ap = network.WLAN(network.AP_IF)
    ap.config(essid=ssid, password=password) 
    ap.active(True)

    while ap.active == False:
        pass
    print("Access point active")
    print(ap.ifconfig())
    led.on()
    return '192.168.4.1'

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
    html = """<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>PicoBot Control</title>
<style>
* { box-sizing: border-box; }
body { 
    font-family: Arial, sans-serif; 
    text-align: center; 
    background: #f4f4f9;
    margin: 0;
    padding: 10px;
    touch-action: manipulation;
}
h1 { font-size: 2.2em; margin: 15px 0; }
h3 { font-size: 1.8em; margin: 20px 0 10px 0; }

.control-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    max-width: 800px;
    margin: 0 auto;
    padding: 10px;
}

.control-btn {
    height: 100px;
    width: 100%;
    font-size: 1.4em;
    background: #007bff;
    color: white;
    border: none;
    border-radius: 15px;
    cursor: pointer;
    touch-action: manipulation;
    padding: 10px;
    margin: 0;
}
.control-btn:active { background: #0056b3; }

.stop-btn { background: #dc3545; }
.stop-btn:active { background: #c82333; }

.slider-container {
    margin: 20px auto;
    padding: 15px;
    background: white;
    border-radius: 15px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    max-width: 500px;
}

.slider-label {
    font-size: 1.4em;
    font-weight: bold;
    margin-bottom: 15px;
    display: block;
}

.slider {
    width: 100%;
    height: 50px;
    margin: 15px 0;
}

.slider-value {
    font-size: 1.4em;
    font-weight: bold;
    margin-top: 10px;
    display: inline-block;
    min-width: 50px;
}

#reset {
    background: #ff5733;
    height: 70px;
    width: 200px;
    font-size: 1.4em;
    border-radius: 15px;
    margin: 20px auto;
}
#reset:active { background: #c70039; }

@media (max-width: 600px) {
    .control-btn { height: 90px; font-size: 1.2em; }
    h1 { font-size: 1.8em; }
    h3 { font-size: 1.5em; }
}
</style>
</head>
<body>
<h1>🤖 PicoBot Control</h1>

<div class="control-grid">
    <button class="control-btn" onclick="c('left_forward')">↖️ L-Fwd</button>
    <button class="control-btn" onclick="c('forward')">⬆️ Forward</button>
    <button class="control-btn" onclick="c('right_forward')">↗️ R-Fwd</button>

    <button class="control-btn" onclick="c('left')">⬅️ Left</button>
    <button class="control-btn stop-btn" onclick="c('stop')">⏹️ STOP</button>
    <button class="control-btn" onclick="c('right')">➡️ Right</button>

    <button class="control-btn" onclick="c('left_back')">↙️ L-Back</button>
    <button class="control-btn" onclick="c('back')">⬇️ Back</button>
    <button class="control-btn" onclick="c('right_back')">↘️ R-Back</button>

    <button class="control-btn" onclick="c('rotate_left')">🔄 Rot-L</button>
    <button class="control-btn stop-btn" onclick="c('stop')">⏹️ STOP</button>
    <button class="control-btn" onclick="c('rotate_right')">🔃 Rot-R</button>
</div>

<h3>🦾 Arm Control</h3>

<div class="slider-container">
    <span class="slider-label">Base:</span>
    <input type="range" class="slider" id="base_slider" min="0" max="180" value="90" onchange="s('base',this.value)">
    <span class="slider-value" id="base_value">90°</span>
</div>

<div class="slider-container">
    <span class="slider-label">Arm:</span>
    <input type="range" class="slider" id="arm_slider" min="40" max="140" value="90" onchange="s('arm',this.value)">
    <span class="slider-value" id="arm_value">90°</span>
</div>

<div class="slider-container">
    <span class="slider-label">Claw:</span>
    <input type="range" class="slider" id="claw_slider" min="40" max="140" value="90" onchange="s('claw',this.value)">
    <span class="slider-value" id="claw_value">90°</span>
</div>

<button id="reset" onclick="resetAll()">🔄 Reset All</button>

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
        response = urequests.post(
            REPORT_URL,
            headers={'Content-Type': 'application/json'},
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
        if time.ticks_diff(time.ticks_ms(), last_report) >= REPORT_DELAY * 1000:
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
    # For STA mode
    #ip = connect()
    # For AP mode
    ip = create_WiFi_AP()
    connection = open_socket(ip)
    print(f'Reporting status to {REPORT_URL} every {REPORT_DELAY}s')
    serve(connection)
except KeyboardInterrupt:
    machine.reset()