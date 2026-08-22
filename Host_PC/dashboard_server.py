#!/usr/bin/env python3
"""
Rescue Robot — Cognitive Telemetry Dashboard Server v2.1
- Reads 18-byte sensor packets + 4-byte RSSI from BluePill (LoRa RX)
- Streams to browser via WebSocket with RViz-style spatial markers
- Hazard zones: flame (2m ahead), gas/temp (2m radius), human (radar distance)
"""
import glob, struct, threading, time, math, serial, json
from collections import deque
from flask import Flask, send_from_directory, jsonify
from flask_socketio import SocketIO

ROS2_AVAILABLE = False
try:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String
    ROS2_AVAILABLE = True
except ImportError:
    pass

app = Flask(__name__, static_folder='dashboard_ui', template_folder='dashboard_ui')
app.config['SECRET_KEY'] = 'rescue_robot_2025'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ── State ────────────────────────────────────────────────────────────
state = {
    'x': 0.0, 'y': 0.0, 'flame': False, 'human': False,
    'gas_adc': 0, 'radar_dist': 0, 'temp': 0,
    'rssi': -120, 'packet_count': 0, 'uptime': 0,
    'start_time': time.time(), 'connected': False, 'port': None,
}

event_log = deque(maxlen=100)
breadcrumbs = deque(maxlen=500)
last_bc_time = 0

# ── Spatial Memory (same logic as wired_sensors_node.py / RViz) ──────
flame_db = []       # {'id':int, 'x':float, 'y':float}
gas_db = []
temp_db = []
human_db = []
next_ids = {'flame': 0, 'gas': 0, 'temp': 0, 'human': 0}

# Simulated yaw (direction the robot is "looking")
# We estimate it from successive positions
prev_pos = None
est_yaw = 0.0

def find_port():
    ports = glob.glob('/dev/ttyACM*') + glob.glob('/dev/ttyUSB*')
    if '/dev/ttyACM1' in ports:
        return '/dev/ttyACM1'
    return ports[0] if ports else None

def add_event(kind, msg, x=None, y=None):
    ev = {'time': time.strftime('%H:%M:%S'), 'kind': kind, 'msg': msg,
          'x': round(x,2) if x is not None else None,
          'y': round(y,2) if y is not None else None}
    event_log.appendleft(ev)
    socketio.emit('event', ev)

def maybe_breadcrumb(x, y):
    global last_bc_time
    now = time.time()
    if now - last_bc_time >= 5:
        c = {'x': round(x,2), 'y': round(y,2), 't': int(now)}
        breadcrumbs.append(c)
        socketio.emit('breadcrumb', c)
        last_bc_time = now

def estimate_yaw(x, y):
    """Estimate heading from successive positions."""
    global prev_pos, est_yaw
    if prev_pos is not None:
        dx = x - prev_pos[0]
        dy = y - prev_pos[1]
        if math.hypot(dx, dy) > 0.05:
            est_yaw = math.atan2(dy, dx)
    prev_pos = (x, y)
    return est_yaw

def dist(x1, y1, x2, y2):
    return math.hypot(x1 - x2, y1 - y2)

# ── Spatial Marker Logic (mirrors wired_sensors_node.py) ─────────────
def process_spatial(rx, ry, flame, human, gas_adc, radar_dist, temp):
    """Process sensor data and manage spatial hazard markers exactly like RViz."""
    yaw = estimate_yaw(rx, ry)
    markers_changed = False

    # ── FLAME: placed 2m ahead of robot ──────────────────────────────
    target_x = rx + 2.0 * math.cos(yaw)
    target_y = ry + 2.0 * math.sin(yaw)

    if flame:
        exists = any(dist(target_x, target_y, f['x'], f['y']) <= 1.0 for f in flame_db)
        if not exists:
            fid = next_ids['flame']; next_ids['flame'] += 1
            entry = {'id': fid, 'x': round(target_x,2), 'y': round(target_y,2),
                     'kind': 'flame', 'color': 'red', 'radius': 0.5, 'label': '🔥'}
            flame_db.append(entry)
            socketio.emit('marker_add', entry)
            add_event('flame', f'🔥 FLAME at ({target_x:.1f},{target_y:.1f})', target_x, target_y)
            markers_changed = True
    else:
        to_rm = [i for i,f in enumerate(flame_db) if dist(target_x, target_y, f['x'], f['y']) <= 1.0]
        for i in sorted(to_rm, reverse=True):
            socketio.emit('marker_del', {'kind': 'flame', 'id': flame_db[i]['id']})
            add_event('info', '✅ Flame cleared')
            del flame_db[i]
            markers_changed = True

    # ── GAS: zone at robot position, 2m radius ───────────────────────
    if gas_adc >= 650:
        # Color: green if 650-720, purple if >=721
        if gas_adc >= 721:
            col = 'purple'
        else:
            col = 'lime'
        exists = any(dist(rx, ry, g['x'], g['y']) <= 2.0 for g in gas_db)
        if not exists:
            gid = next_ids['gas']; next_ids['gas'] += 1
            entry = {'id': gid, 'x': round(rx,2), 'y': round(ry,2),
                     'kind': 'gas', 'color': col, 'radius': 2.0, 'label': '☁️',
                     'extra': str(gas_adc)}
            gas_db.append(entry)
            socketio.emit('marker_add', entry)
            add_event('gas', f'⚠️ Toxic gas ADC={gas_adc}', rx, ry)
            markers_changed = True
    else:
        to_rm = [i for i,g in enumerate(gas_db) if dist(rx, ry, g['x'], g['y']) <= 2.0]
        for i in sorted(to_rm, reverse=True):
            socketio.emit('marker_del', {'kind': 'gas', 'id': gas_db[i]['id']})
            add_event('info', '✅ Gas cleared')
            del gas_db[i]
            markers_changed = True

    # ── TEMPERATURE: zone at robot position, 2m radius ───────────────
    if temp >= 40:
        col = '#ff0000' if temp > 70 else '#ff8000'
        exists = any(dist(rx, ry, t['x'], t['y']) <= 2.0 for t in temp_db)
        if not exists:
            tid = next_ids['temp']; next_ids['temp'] += 1
            entry = {'id': tid, 'x': round(rx,2), 'y': round(ry,2),
                     'kind': 'temp', 'color': col, 'radius': 2.0, 'label': '🌡️',
                     'extra': f'{temp}°C'}
            temp_db.append(entry)
            socketio.emit('marker_add', entry)
            add_event('temp', f'🌡️ High temp {temp}°C', rx, ry)
            markers_changed = True
    else:
        to_rm = [i for i,t in enumerate(temp_db) if dist(rx, ry, t['x'], t['y']) <= 2.0]
        for i in sorted(to_rm, reverse=True):
            socketio.emit('marker_del', {'kind': 'temp', 'id': temp_db[i]['id']})
            add_event('info', '✅ Area cooled')
            del temp_db[i]
            markers_changed = True

    # ── HUMAN: placed at radar_dist ahead of robot ───────────────────
    human_x = rx + (radar_dist / 100.0) * math.cos(yaw)
    human_y = ry + (radar_dist / 100.0) * math.sin(yaw)

    if human:
        exists = any(dist(human_x, human_y, h['x'], h['y']) <= 1.5 for h in human_db)
        if not exists:
            hid = next_ids['human']; next_ids['human'] += 1
            entry = {'id': hid, 'x': round(human_x,2), 'y': round(human_y,2),
                     'kind': 'human', 'color': 'cyan', 'radius': 0.6, 'label': '🧍',
                     'extra': f'{radar_dist}cm'}
            human_db.append(entry)
            socketio.emit('marker_add', entry)
            add_event('human', f'🧍 HUMAN at {radar_dist}cm', human_x, human_y)
            markers_changed = True
    else:
        to_rm = [i for i,h in enumerate(human_db) if dist(rx, ry, h['x'], h['y']) <= 2.5]
        for i in sorted(to_rm, reverse=True):
            socketio.emit('marker_del', {'kind': 'human', 'id': human_db[i]['id']})
            add_event('info', '✅ Human left area')
            del human_db[i]
            markers_changed = True

# ── Serial Reader ────────────────────────────────────────────────────
def serial_reader():
    buf = bytearray()
    while True:
        port = find_port()
        if not port:
            state['connected'] = False
            socketio.emit('status', {'connected': False, 'port': 'No device'})
            time.sleep(2); continue
        try:
            ser = serial.Serial(port, 9600, timeout=0.05)
            state['connected'] = True; state['port'] = port
            state['start_time'] = time.time()
            socketio.emit('status', {'connected': True, 'port': port})
            add_event('info', f'Connected to {port}')
            print(f'[SRV] Connected to {port}')

            while True:
                chunk = ser.read(64)
                if chunk: buf.extend(chunk)
                while len(buf) >= 4:
                    if buf[0] == 0xAB and buf[1] == 0xCD:
                        # Try parsing as an 18-byte packet
                        parsed = False
                        if not parsed and len(buf) >= 20:
                            pkt = bytes(buf[:20])
                            pay = pkt[2:19]
                            cs = 0
                            for b in pay: cs ^= b
                            if cs == pkt[19]:
                                try:
                                    rx, ry, fl, hu, seq, ga, rd, tp = struct.unpack('<ffBBHHHB', pay)
                                    print(f"[SRV] LoRa 20-byte Decoded: x={rx:.2f}, y={ry:.2f}, flame={fl}, human={hu}, seq={seq}, gas={ga}, radar={rd}, temp={tp}")
                                    state.update({
                                        'x': round(float(rx),3), 'y': round(float(ry),3),
                                        'flame': bool(fl), 'human': bool(hu),
                                        'gas_adc': int(ga), 'radar_dist': int(rd), 'temp': int(tp)
                                    })
                                    state['packet_count'] += 1
                                    state['uptime'] = int(time.time() - state['start_time'])
                                    maybe_breadcrumb(rx, ry)
                                    process_spatial(rx, ry, fl, hu, ga, rd, tp)
                                    socketio.emit('telemetry', {
                                        'x': state['x'], 'y': state['y'],
                                        'flame': state['flame'], 'human': state['human'],
                                        'gas_adc': state['gas_adc'], 'radar_dist': state['radar_dist'],
                                        'temp': state['temp'], 'rssi': state['rssi'],
                                        'packet_count': state['packet_count'], 'uptime': state['uptime']
                                    })
                                    parsed = True
                                    buf = buf[20:]
                                except struct.error:
                                    pass

                        if not parsed:
                            if len(buf) >= 18:
                                # Neither checksum matched, discard header byte to keep scanning
                                buf.pop(0)
                            else:
                                # Not enough bytes yet, wait for more data
                                break

                    elif buf[0] == 0xEE and buf[1] == 0xFF and len(buf) >= 4:
                        state['rssi'] = buf[2] - 157
                        socketio.emit('rssi', {'rssi': state['rssi']})
                        buf = buf[4:]
                    else:
                        buf.pop(0)
        except serial.SerialException as e:
            print(f'[SRV] Serial error: {e}')
            state['connected'] = False
            socketio.emit('status', {'connected': False, 'port': str(e)})
            time.sleep(3)

# ── ROS2 Reader (Simulation + Real Robot Telemetry Bridge) ───────────
# ── ROS2 Reader (Simulation Fallback) ────────────────────────────────
def ros2_reader():
    if not ROS2_AVAILABLE:
        return
    print("[SRV] Initializing ROS2 telemetry listener...")
    rclpy.init()
    node = Node('dashboard_ros2_bridge')
    
    def telemetry_callback(msg):
        try:
            data = json.loads(msg.data)
            rx = data.get('x', 0.0)
            ry = data.get('y', 0.0)
            fl = data.get('flame', False)
            hu = data.get('human', False)
            ga = data.get('gas_adc', 0)
            rd = data.get('radar_dist', 0)
            tp = data.get('temp', 0)
            rs = data.get('rssi', -55)
            
            state.update({
                'x': round(float(rx), 3), 'y': round(float(ry), 3),
                'flame': bool(fl), 'human': bool(hu),
                'gas_adc': int(ga), 'radar_dist': int(rd), 'temp': int(tp),
                'rssi': int(rs)
            })
            state['packet_count'] += 1
            if state['uptime'] == 0:
                state['start_time'] = time.time()
            state['uptime'] = int(time.time() - state['start_time'])
            state['connected'] = True
            state['port'] = 'ROS2 Sim'
            
            maybe_breadcrumb(rx, ry)
            process_spatial(rx, ry, fl, hu, ga, rd, tp)
            
            socketio.emit('status', {'connected': True, 'port': 'ROS2 Sim'})
            socketio.emit('telemetry', {
                'x': state['x'], 'y': state['y'],
                'flame': state['flame'], 'human': state['human'],
                'gas_adc': state['gas_adc'], 'radar_dist': state['radar_dist'],
                'temp': state['temp'], 'rssi': state['rssi'],
                'packet_count': state['packet_count'], 'uptime': state['uptime']
            })
        except Exception as e:
            print(f"[SRV] Error parsing ROS2 telemetry: {e}")

    node.create_subscription(String, '/robot/telemetry', telemetry_callback, 10)
    try:
        rclpy.spin(node)
    except Exception as e:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


@socketio.on('connect')
def handle_connect():
    # Send all existing markers to newly connected client
    for m in flame_db + gas_db + temp_db + human_db:
        socketio.emit('marker_add', m)
    # Send current status and telemetry immediately
    socketio.emit('status', {'connected': state['connected'], 'port': state['port']})
    socketio.emit('telemetry', {
        'x': state['x'], 'y': state['y'],
        'flame': state['flame'], 'human': state['human'],
        'gas_adc': state['gas_adc'], 'radar_dist': state['radar_dist'],
        'temp': state['temp'], 'rssi': state['rssi'],
        'packet_count': state['packet_count'], 'uptime': state['uptime']
    })

@socketio.on('goto')
def handle_goto(data):
    add_event('info', f"🎯 Target: ({data.get('x',0):.1f}, {data.get('y',0):.1f})")

@socketio.on('return_home')
def handle_rth():
    add_event('info', '🏠 Return-to-Home command')
    socketio.emit('rth_trail', list(breadcrumbs))

@app.route('/')
def index(): return send_from_directory('dashboard_ui', 'index.html')

@app.route('/api/events')
def api_ev(): return jsonify(list(event_log))

@app.route('/api/markers')
def api_mk(): return jsonify(flame_db + gas_db + temp_db + human_db)

if __name__ == '__main__':
    threading.Thread(target=serial_reader, daemon=True).start()
    if ROS2_AVAILABLE:
        threading.Thread(target=ros2_reader, daemon=True).start()
    print('[SRV] Cognitive Dashboard → http://localhost:5000')
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False)
