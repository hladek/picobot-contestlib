
# 1. Introduction

Communication protocols are a fundamental component of modern robotic systems, enabling reliable information exchange between robots, users, supervisory applications, and cloud-based services. The design of an appropriate communication protocol directly influences the reliability, scalability, and usability of a robotic platform. While advanced robotic systems often rely on sophisticated middleware such as the Robot Operating System (ROS 2) or industrial communication standards, educational and embedded robotic platforms frequently require lightweight solutions that can operate efficiently on resource-constrained hardware while remaining simple to deploy and maintain.

The PicoBot system was developed as an educational mobile robotic platform intended for robotics competitions, laboratory exercises, and classroom demonstrations. In addition to local manual control through a web interface, the platform supports centralized competition management, allowing multiple robots to participate simultaneously in remotely supervised tasks. These application scenarios impose several functional requirements on the communication infrastructure, including reliable robot identification, secure communication with a competition server, synchronized competition control, centralized timing, and compatibility with standard Internet technologies.

To satisfy these requirements, PicoBot employs a two-layer communication architecture. The first communication layer enables direct interaction between the robot and a web browser using a lightweight HTTP-based control interface. This interface allows an operator to issue movement commands and manipulate the robot's servo-driven arm without requiring dedicated client software. The second communication layer provides periodic status reporting from the robot to a centralized competition server using HTTPS and JSON-encoded messages. Through this channel, the server monitors robot activity, authenticates participating devices, coordinates competition state transitions, and distributes competition control commands.

The proposed protocol intentionally prioritizes simplicity, portability, and interoperability over the advanced capabilities offered by general-purpose robotic middleware. By relying exclusively on widely supported Internet protocols, the system can be operated from virtually any modern web browser while requiring only modest computational and memory resources on the embedded robot controller. This design significantly reduces software complexity and facilitates deployment in educational environments where ease of installation and maintenance is an important consideration.

The communication protocol is designed to satisfy the following principal requirements:

* unique identification and optional authentication of participating robots;
* synchronized competition start and centralized competition management;
* automatic timing and recording of competition events;
* reliable transmission of robot status information over standard IP networks;
* compatibility with low-cost embedded hardware and standard web technologies.

This document specifies the complete PicoBot communication protocol, including the local browser control interface, the robot-to-server communication protocol, the competition server application programming interface (API), authentication mechanisms, and protocol behaviour under normal and exceptional operating conditions. Furthermore, the document discusses the protocol design in the context of existing communication technologies used in robotics and justifies the architectural decisions adopted for the PicoBot platform.

The remainder of this document is organized as follows. Section 2 reviews the current state of the art in robotic communication protocols and positions the proposed solution relative to existing technologies. Section 3 analyzes the functional requirements that guided the protocol design. Section 4 presents the overall communication architecture, followed by detailed specifications of the browser control protocol and the robot-to-server communication protocol. Subsequent sections describe the competition server API, authentication mechanisms, sequence diagrams illustrating typical communication scenarios, and considerations regarding reliability, security, and future protocol extensions.


## 2. Protocol Requirements Analysis

The PicoBot communication protocol was designed to satisfy the functional requirements of educational robotics competitions while remaining lightweight enough for execution on resource-constrained embedded hardware such as the Raspberry Pi Pico W. The protocol addresses five primary requirements.

### 2.1 Robot Authentication

Each robot participating in a competition must be uniquely identifiable to prevent duplicate registrations and unauthorized devices from influencing the competition.

The protocol achieves this through two complementary mechanisms:

* every status report includes the robot's unique MAC address, which serves as the primary identifier;
* optional bearer-token authentication verifies that status reports originate from authorized firmware instances.

The competition server maintains an internal mapping between robot identities and their reported states, enabling persistent tracking throughout the competition. When authentication is enabled, requests lacking the correct `Authorization: Bearer <token>` header are rejected with an HTTP 401 (Unauthorized) response.

This approach provides sufficient security for educational and laboratory environments while maintaining minimal implementation complexity.

---

### 2.2 Synchronized Competition Start

A key requirement of robotics competitions is ensuring that all robots begin under identical conditions.

Instead of initiating robot movement directly from the server, the protocol periodically distributes a competition state encoded as a compact bitmask. Each robot independently interprets this value to determine whether the competition is:

* idle,
* prepared but not yet started, or
* actively running.

The transition from the *ready* state (`1`) to the *running* state (`3`) acts as a synchronization signal for all connected robots. Since every robot polls the server at regular intervals, all devices receive the updated state within one reporting period, providing sufficiently synchronized starts for educational competitions without requiring dedicated real-time synchronization protocols.

---

### 2.3 Automatic Timing

The protocol separates competition management from robot execution.

The competition server records the official competition start and stop times independently of the robots. Consequently, robots do not require synchronized clocks or external time references.

Each status report includes the robot uptime (`uptime_ms`), allowing operators to monitor robot operation and detect unexpected resets. Official competition timing is maintained exclusively by the server, eliminating errors caused by unsynchronized local clocks.

This centralized timing model simplifies firmware implementation while ensuring consistent timing across all participating robots.

---

### 2.4 Transmission of Completion Times

The protocol supports automatic determination of competition results through periodic status reporting.

When a robot completes its assigned task, the competition server records the completion event together with its server-side timestamp. Since all timestamps are generated by the same server clock, measured completion times remain directly comparable across all robots.

Separating timestamp generation from robot firmware also prevents timing discrepancies caused by oscillator drift or processor load on individual robots.

Future protocol versions may extend the status message with explicit task-completion indicators or additional performance metrics without affecting backward compatibility.

---

### 2.5 Reliable Internet Communication

Unlike purely local remote-control protocols, the PicoBot competition protocol is designed to operate across standard IP networks, including the public Internet.

Reliability is achieved through several design choices:

* HTTPS provides reliable transport over TCP together with transport-layer encryption.
* Periodic status reporting ensures that temporary packet loss or network interruptions are automatically corrected during the next reporting interval.
* Communication is stateless, allowing any failed request to be retried without maintaining persistent sessions.
* The robot preserves the last valid competition state if communication temporarily fails, preventing unexpected behavior caused by transient network outages.

This design prioritizes robustness and simplicity over strict real-time guarantees, making it appropriate for educational competitions and remote laboratory deployments where occasional communication delays are acceptable.

---

### Summary

The proposed communication protocol satisfies the principal functional requirements of educational robotics competitions by combining lightweight HTTP/HTTPS communication with centralized competition management. The resulting architecture provides authenticated robot identification, synchronized competition control, centralized timing, reliable result collection, and Internet-capable communication while remaining sufficiently simple to execute on low-cost embedded hardware with limited computational resources.


| Requirement                    | Mechanism                                                 | Protocol Component              |
| ------------------------------ | --------------------------------------------------------- | ------------------------------- |
| Robot authentication           | MAC address + optional Bearer token                       | HTTP Authorization header       |
| Unique robot identification    | MAC address                                               | Status JSON                     |
| Synchronized competition start | Competition state bitmask                                 | Server response (`0`, `1`, `3`) |
| Automatic timing               | Centralized server timestamps                             | Competition server              |
| Completion time recording      | Server-side event logging                                 | Competition database            |
| Reliable communication         | HTTPS over TCP with periodic reporting                    | Robot → Server protocol         |
| Fault tolerance                | Retry on next reporting interval; retain last valid state | Robot firmware                  |



## 1. State of the Art

Communication protocols are fundamental components of modern robotic systems, enabling information exchange between robots, operators, cloud services, and supervisory control systems. The choice of a communication protocol depends on application requirements, including latency, reliability, scalability, computational resources, and network topology. Consequently, numerous communication approaches have been developed, ranging from lightweight request-response protocols for embedded systems to sophisticated middleware platforms supporting distributed autonomous robots.

One of the simplest and most widely adopted approaches is the use of the Hypertext Transfer Protocol (HTTP), particularly through RESTful interfaces. Owing to its simplicity, platform independence, and universal support by web browsers and networking libraries, HTTP has become a common solution for controlling educational robots, Internet of Things (IoT) devices, and embedded systems. REST-based interfaces expose robot functions as web resources that can be accessed using standard HTTP methods, allowing developers to control robots directly from a browser without requiring specialized client software. Although this approach simplifies implementation and debugging, the request-response communication model introduces additional latency and makes HTTP less suitable for applications requiring deterministic real-time control or high-frequency command transmission [1,2].

To overcome the limitations of repeated HTTP requests, many robotic applications employ the WebSocket protocol, which enables persistent, full-duplex communication over a single TCP connection. Unlike HTTP, WebSocket allows both the robot and the client application to transmit data asynchronously without repeatedly establishing new connections. This significantly reduces communication overhead and latency, making WebSocket particularly suitable for teleoperation, live telemetry, browser-based dashboards, and video streaming. However, maintaining persistent connections increases firmware complexity and resource consumption, which may be challenging for low-cost microcontroller platforms [3].

Another widely adopted communication technology in robotics and IoT is the Message Queuing Telemetry Transport (MQTT) protocol. MQTT follows a publish-subscribe communication model in which devices exchange messages through a centralized broker rather than communicating directly. This architecture provides excellent scalability and enables efficient asynchronous communication among large numbers of devices while minimizing network bandwidth requirements. Consequently, MQTT has become a standard solution for cloud robotics, fleet management, remote monitoring, and distributed sensor networks. Nevertheless, its deployment requires an additional broker service, increasing overall system complexity compared with direct client-server communication [4].

Research and industrial robotic systems are increasingly built upon the Robot Operating System (ROS) and its successor, ROS 2. Rather than defining a single communication protocol, ROS provides a middleware framework supporting multiple communication paradigms, including publish-subscribe topics, request-response services, and long-running actions. ROS 2 adopts the Data Distribution Service (DDS) as its underlying communication layer, enabling decentralized discovery, configurable Quality of Service (QoS), and deterministic message delivery. These features make ROS 2 highly suitable for autonomous robots, collaborative robotic systems, and distributed research platforms. However, the computational and memory requirements of ROS 2 generally exceed the capabilities of resource-constrained microcontrollers such as the Raspberry Pi Pico W, necessitating more powerful processors or dedicated gateway devices [5,6].

DDS itself represents the current state of the art in industrial real-time distributed communication. Standardized by the Object Management Group (OMG), DDS provides brokerless publish-subscribe communication with configurable reliability, durability, latency, and fault tolerance through an extensive set of Quality of Service policies. These capabilities have led to its adoption in autonomous vehicles, aerospace systems, industrial automation, and safety-critical applications where deterministic communication is essential. The complexity of DDS, however, makes it unsuitable for many educational robotic platforms with limited computational resources [7].

The communication protocol proposed for the PicoBot system intentionally adopts a significantly simpler architecture. Instead of employing publish-subscribe middleware or persistent communication channels, it combines lightweight HTTP communication for local browser-based robot control with periodic HTTPS reporting to a centralized competition server. This architecture minimizes firmware complexity while preserving compatibility with standard web technologies and requiring no additional middleware, brokers, or specialized software. Although this design does not provide the deterministic performance of DDS or the flexibility of ROS 2, it satisfies the functional requirements of educational robotics competitions, including authenticated robot identification, synchronized competition control, centralized timing, and reliable communication over conventional IP networks. The resulting protocol therefore represents a pragmatic trade-off between implementation simplicity, portability, and functionality, making it particularly suitable for resource-constrained embedded robots used in educational environments.

### References

[1] Fielding, R. T. *Architectural Styles and the Design of Network-based Software Architectures*. University of California, Irvine, 2000.

[2] IETF. *RFC 9110: HTTP Semantics*. 2022.

[3] IETF. *RFC 6455: The WebSocket Protocol*. 2011.

[4] OASIS. *MQTT Version 5.0*. OASIS Standard, 2019.

[5] Quigley, M., et al. "ROS: an Open-Source Robot Operating System." *ICRA Workshop on Open Source Software*, 2009.

[6] Macenski, S., et al. "Robot Operating System 2: Design, Architecture, and Uses in the Wild." *Science Robotics*, 7(66), eabm6074, 2022.

[7] Object Management Group. *Data Distribution Service (DDS) Version 1.4*. OMG Specification, 2015.


# PicoBot Communication Protocol

This document describes all communication protocols used in the PicoBot system.  
There are two independent protocol layers:

1. **Robot ↔ Browser** — HTTP control protocol (port 80, on-board web server)
2. **Robot ↔ Competition Server** — HTTPS status/command protocol (configurable URL)

---

## 1. Robot ↔ Browser Control Protocol

The PicoBot runs a minimal HTTP/1.0 server on **port 80**.  
A phone or browser on the same Wi-Fi network sends plain HTTP GET requests to control the robot.

### 1.1 General Request Format

```
GET /<command>? HTTP/1.1
Host: <robot-ip>
```

Every control URL ends with a `?` (even when there are no query parameters). This is an implementation detail of the on-board request parser.

### 1.2 Movement Commands

Each request triggers a motor action followed by a 100 ms automatic stop.

| URL path | Action |
|----------|--------|
| `/forward?` | All four wheels forward |
| `/back?` | All four wheels backward |
| `/left?` | Turn / strafe left |
| `/right?` | Turn / strafe right |
| `/left_forward?` | Diagonal left-forward |
| `/right_forward?` | Diagonal right-forward |
| `/left_back?` | Diagonal left-backward |
| `/right_back?` | Diagonal right-backward |
| `/rotate_left?` | Rotate left on the spot |
| `/rotate_right?` | Rotate right on the spot |
| `/stop?` | Hard stop — all motors off immediately |

**Example:**
```
GET /forward? HTTP/1.1
Host: 192.168.1.42
```

### 1.3 Servo Arm Commands

Servo positions are sent as query parameters appended to the root path.

| Parameter | Servo | Valid range | Description |
|-----------|-------|-------------|-------------|
| `servo_base_slider=<angle>` | Channel 0 (base) | 0 – 180 | Rotate the arm base |
| `servo_arm_slider=<angle>` | Channel 1 (arm) | 40 – 140 | Raise or lower the arm |
| `servo_claw_slider=<angle>` | Channel 2 (claw) | 40 – 140 | Open or close the claw |

Values outside the valid range are silently clamped to the nearest limit.  
All three parameters may be combined in one request.

**Example — set base to 45°:**
```
GET /?servo_base_slider=45 HTTP/1.1
Host: 192.168.1.42
```

**Example — set arm and claw together:**
```
GET /?servo_arm_slider=100&servo_claw_slider=60 HTTP/1.1
Host: 192.168.1.42
```

### 1.4 Reset Command

```
GET /reset_to_default? HTTP/1.1
Host: 192.168.1.42
```

Returns all three servos smoothly to 90°.

### 1.5 Response Format

Every request — regardless of the command — receives the same response: the full HTML control page.

```
HTTP/1.0 200 OK
Content-type: text/html

<!DOCTYPE html>…
```

On internal errors the robot responds with:
```
HTTP/1.0 500 Internal Server Error
Content-type: text/plain

Server Error
```

### 1.6 Lock Behaviour (`SERVER_BRAKE`)

When `SERVER_BRAKE = True` in `picobot_config.py` **and** `server_competition_running` is `False`, the robot silently ignores all movement and servo commands received over the control protocol.  
The HTML page reflects this state with a lock overlay.

---

## 2. Robot → Competition Server Status Protocol

When `SERVER_ENABLE = True`, the robot periodically POSTs its current state to the competition server and receives back a command integer.

### 2.1 Request

| Property | Value |
|----------|-------|
| Method | `POST` |
| URL | Configured in `REPORT_URL` (must be `https://`) |
| Content-Type | `application/json` |
| Interval | Every `REPORT_DELAY` seconds (default: 10 s) |

#### Headers

```
Content-Type: application/json
Authorization: Bearer <token>          ← only when REPORT_AUTH is set
```

#### JSON Body

```json
{
  "mac":        "aa:bb:cc:dd:ee:ff",
  "ip":         "192.168.1.42",
  "servo_base": 90,
  "servo_arm":  90,
  "servo_claw": 90,
  "uptime_ms":  12345
}
```

| Field | Type | Description |
|-------|------|-------------|
| `mac` | string | Wireless adapter MAC address (lowercase, colon-separated) |
| `ip` | string | IP address assigned by the Wi-Fi router |
| `servo_base` | integer | Current base servo angle in degrees |
| `servo_arm` | integer | Current arm servo angle in degrees |
| `servo_claw` | integer | Current claw servo angle in degrees |
| `uptime_ms` | integer | Milliseconds since boot (`time.ticks_ms()`) |

### 2.2 Response

The server responds with a **plain-text integer** (no JSON wrapper, no newlines except possibly a trailing one).

```
HTTP/1.1 200 OK
Content-Type: text/plain

3
```

| HTTP status | Meaning |
|-------------|---------|
| `200` | Accepted; body contains the command integer |
| `400` | Bad request — `mac` field missing or body not valid JSON |
| `401` | Unauthorized — `Authorization` header missing or wrong token |

### 2.3 Server Command Bitmask

The integer is interpreted as a bitmask. The robot stores the raw value in `server_command` and derives the two boolean flags:

| Bit | Mask | Boolean variable | Meaning |
|-----|------|-----------------|---------|
| 0 (LSB) | `0x01` | `server_competition_ready` | Competition is prepared and about to start |
| 1 | `0x02` | `server_competition_running` | Competition is actively running |

**Possible values:**

| Response | `server_competition_ready` | `server_competition_running` | State |
|----------|---------------------------|------------------------------|-------|
| `0` | `False` | `False` | Idle — no active competition |
| `1` | `True` | `False` | Competition ready, not yet started |
| `3` | `True` | `True` | Competition running |

> Note: value `2` (running but not ready) is not produced by the reference server implementation but is not rejected by the firmware.

### 2.4 Error Handling

If the POST fails for any reason (network error, timeout, non-200 status), the robot:
- sets `server_online = False`
- leaves `server_command`, `server_competition_ready`, and `server_competition_running` at their last known values
- retries after the next `REPORT_DELAY` interval

---

## 3. Competition Server API (Server-side endpoints)

The Flask server (`Server/app.py`) exposes the following HTTP endpoints.

### 3.1 Robot Status Receiver

```
POST /picobot/status
```

Receives status reports from robots (see §2.1). The endpoint path is configurable via `STATUS_ENDPOINT` in `Server/config.py`.

Returns the competition command integer derived from the current competition state:

| Competition state | Returned integer |
|-------------------|-----------------|
| No active competition | `DEFAULT_COMMAND` (default `0`) |
| Competition created, not started | `1` (`competition_ready`) |
| Competition started, not ended | `3` (`competition_ready` + `competition_running`) |

### 3.2 Dashboard

```
GET /
```

Displays a live table of all robots that have ever reported in, with their latest servo positions, uptime, IP address, and current command state.

### 3.3 Robot Detail

```
GET /robot/<mac>
```

Shows the full request history for a single robot identified by its MAC address.

### 3.4 Competition Management

| Method | Path | Action |
|--------|------|--------|
| `GET` | `/competition` | View active and past competitions |
| `POST` | `/competition/create` | Create a new competition (form field: `name`) |
| `POST` | `/competition/<id>/start` | Start a created competition |
| `POST` | `/competition/<id>/stop` | Stop or cancel a competition |

---

## 4. Authentication

Both sides support an optional shared secret configured independently.

### Robot side (`picobot_config.py`)

```python
REPORT_AUTH = 'mysecret'   # or None to disable
```

When set, the robot adds to every POST request:
```
Authorization: Bearer mysecret
```

### Server side (`Server/config.py`)

```python
REPORT_AUTH = 'mysecret'   # or None to accept all requests
```

When set, the server rejects any POST to `/picobot/status` that does not carry the exact matching `Authorization: Bearer <token>` header with `401 Unauthorized`.

---

## 5. Sequence Diagrams

### 5.1 Normal competition flow

```
Robot                         Competition Server
  |                                  |
  |  POST /picobot/status (JSON)     |
  |  { mac, ip, servos, uptime }     |
  |─────────────────────────────────►|
  |                                  | (competition created, not started)
  |◄─────────────────────────────────|
  |  200 OK  body: "1"               |  competition_ready = True
  |                                  |
  |          … admin clicks Start …  |
  |                                  |
  |  POST /picobot/status (JSON)     |
  |─────────────────────────────────►|
  |                                  | (competition running)
  |◄─────────────────────────────────|
  |  200 OK  body: "3"               |  competition_ready = True
  |                                  |  competition_running = True
  |    (controls unlock if SERVER_BRAKE)|
  |                                  |
  |          … admin clicks Stop …   |
  |                                  |
  |  POST /picobot/status (JSON)     |
  |─────────────────────────────────►|
  |◄─────────────────────────────────|
  |  200 OK  body: "0"               |  both flags False
```

### 5.2 Browser control tap

```
Browser (phone)               Robot (port 80)
  |                                  |
  |  GET /forward? HTTP/1.1          |
  |─────────────────────────────────►|
  |                                  | executes goForward() + 100 ms stop
  |◄─────────────────────────────────|
  |  HTTP/1.0 200 OK                 |
  |  Content-type: text/html         |
  |  <full control page HTML>        |
```


# Conclusion

The PicoBot communication protocol provides a lightweight and practical solution for controlling educational mobile robots and managing robotics competitions over standard IP networks. By combining a simple HTTP-based browser interface with secure HTTPS communication between the robot and a centralized competition server, the protocol enables local robot control, authenticated status reporting, synchronized competition management, and centralized timing while maintaining low implementation complexity.

The protocol was specifically designed for resource-constrained embedded hardware, avoiding the computational overhead associated with general-purpose robotic middleware such as ROS 2 or DDS. Although it does not provide deterministic real-time communication or advanced middleware services, it satisfies the functional requirements of educational robotics applications, including robot authentication, synchronized competition start, automatic timing, transmission of competition status, and reliable Internet communication.

The modular architecture and use of widely adopted Internet standards facilitate future protocol extensions while preserving backward compatibility. Possible enhancements include event-driven communication using WebSockets or MQTT, richer telemetry, stronger authentication mechanisms, and support for additional competition management features. These characteristics make the PicoBot communication protocol a suitable foundation for educational robotics platforms, laboratory environments, and small-scale robotic competitions.

