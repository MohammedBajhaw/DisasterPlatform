import rclpy
from rclpy.node import Node
import serial
import struct
import math
import random
from geometry_msgs.msg import PointStamped, PoseStamped, Point
from visualization_msgs.msg import Marker
from std_msgs.msg import Float32, Int32, Bool
from tf2_ros import Buffer, TransformListener

class WiredSensorsNode(Node):
    def __init__(self):
        super().__init__('wired_sensors_node')
        
        # Spatial Memory for flames
        self.flame_markers_db = []
        self.next_flame_id = 0
        
        self.temp_markers_db = []
        self.next_temp_id = 0
        
        self.gas_markers_db = []
        self.next_gas_id = 0
        
        self.human_markers_db = []
        self.next_human_id = 0
        
        # Pre-generate static cloud points to prevent RViz flickering
        self.cloud_points = []
        for _ in range(150):
            ang = random.uniform(0, 2 * math.pi)
            rad = random.uniform(0, 0.8)
            p = Point()
            p.x = rad * math.cos(ang)
            p.y = rad * math.sin(ang)
            p.z = random.uniform(-0.15, 0.15)
            self.cloud_points.append(p)
        
        # Parameters for UART connection to STM32F1 Mini Pill
        self.declare_parameter('serial_port', '/dev/ttyACM0')
        self.declare_parameter('baud_rate', 115200)
        
        port = self.get_parameter('serial_port').value
        baud = self.get_parameter('baud_rate').value
        
        # Publishers
        self.flame_pub = self.create_publisher(Marker, '/local_flame_marker', 10)
        self.human_pub = self.create_publisher(Marker, '/local_human_marker', 10)
        self.pose_pub = self.create_publisher(PoseStamped, '/lora/robot_pose', 10)
        self.gas_pub = self.create_publisher(Float32, '/sensor/gas_voltage', 10)
        self.radar_dist_pub = self.create_publisher(Int32, '/sensor/radar_distance', 10)
        self.radar_motion_pub = self.create_publisher(Bool, '/sensor/radar_motion', 10)
        self.temp_pub = self.create_publisher(Float32, '/sensor/temperature', 10)
        
        self.temp_cloud_pub = self.create_publisher(Marker, '/local_temp_cloud', 10)
        self.gas_cloud_pub = self.create_publisher(Marker, '/local_gas_cloud', 10)
        
        # Raw publishers for Cognitive Intervention Node
        self.raw_flame_pub = self.create_publisher(Bool, '/sensor/flame', 10)
        self.raw_gas_pub = self.create_publisher(Int32, '/sensor/gas', 10)
        self.raw_temp_pub = self.create_publisher(Int32, '/sensor/temp', 10)
        
        # TF Listener to get robot position in map
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        
        try:
            self.serial_conn = serial.Serial(port, baud, timeout=1)
            self.get_logger().info(f"Connected to STM32F4 (BlackPill) on {port} at {baud} baud for WIRED Sensors.")
            
            # Start timer to poll serial
            self.timer = self.create_timer(0.05, self.read_serial) # Faster polling (50ms) for zero-latency wired connection
        except Exception as e:
            self.serial_conn = None
            self.get_logger().error(f"Failed to connect to STM32F4: {e}")
            
        self.buffer = bytearray()
        
    def read_serial(self):
        if self.serial_conn is None or self.serial_conn.in_waiting == 0:
            return
            
        try:
            # Read all available bytes
            data = self.serial_conn.read(self.serial_conn.in_waiting)
            self.buffer.extend(data)
            
            # Process buffer looking for packets
            while len(self.buffer) >= 18:
                # Find header 0xAB 0xCD
                if self.buffer[0] == 0xAB and self.buffer[1] == 0xCD:
                    parsed = False
                    pkt_len = 0
                    
                    # Try 20-byte packet first
                    if len(self.buffer) >= 20:
                        packet = self.buffer[:20]
                        payload = packet[2:19]
                        received_checksum = packet[19]
                        calc_checksum = 0
                        for b in payload: calc_checksum ^= b
                        if calc_checksum == received_checksum:
                            rx, ry, flame, human, seq, gas_adc, radar_dist, temp = struct.unpack('<ffBBHHHB', payload)
                            parsed = True
                            pkt_len = 20
                    
                    # Fallback to 18-byte packet
                    if not parsed and len(self.buffer) >= 18:
                        packet = self.buffer[:18]
                        payload = packet[2:17]
                        received_checksum = packet[17]
                        calc_checksum = 0
                        for b in payload: calc_checksum ^= b
                        if calc_checksum == received_checksum:
                            rx, ry, flame, human, gas_adc, radar_dist, temp = struct.unpack('<ffBBHHB', payload)
                            parsed = True
                            pkt_len = 18
                            
                    if parsed:
                        self.get_logger().info(
                            f"Wired Data: (SimX={rx:.2f}, SimY={ry:.2f}), Flame={flame}, "
                            f"Human={human}, GasADC={gas_adc}, RadarDist={radar_dist}cm, Temp={temp}°C"
                        )
                        
                        # Get real robot pose from SLAM (TF map -> base_link)
                        try:
                            target_frame = 'base_link'
                            try:
                                t = self.tf_buffer.lookup_transform('map', 'base_link', rclpy.time.Time())
                            except:
                                try:
                                    target_frame = 'laser_frame'
                                    t = self.tf_buffer.lookup_transform('map', 'laser_frame', rclpy.time.Time())
                                except:
                                    target_frame = 'odom'
                                    t = self.tf_buffer.lookup_transform('map', 'odom', rclpy.time.Time())

                            real_x = t.transform.translation.x
                            real_y = t.transform.translation.y
                            
                            # Quaternion to yaw
                            q = t.transform.rotation
                            siny_cosp = 2 * (q.w * q.z + q.x * q.y)
                            cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
                            yaw = math.atan2(siny_cosp, cosy_cosp)
                            
                            # Publish Real Robot Pose as /lora/robot_pose
                            pose_msg = PoseStamped()
                            pose_msg.header.stamp = self.get_clock().now().to_msg()
                            pose_msg.header.frame_id = "map"
                            pose_msg.pose.position.x = real_x
                            pose_msg.pose.position.y = real_y
                            pose_msg.pose.position.z = 0.0
                            pose_msg.pose.orientation = q
                            self.pose_pub.publish(pose_msg)
                            
                            # --- SEND SLAM X,Y TO BLACKPILL ---
                            # BlackPill will read this and use it in LoRa telemetry
                            if self.serial_conn and self.serial_conn.is_open:
                                sync = bytearray([0xFA, 0xFB])
                                pack_xy = struct.pack('<ff', real_x, real_y)
                                self.serial_conn.write(sync + pack_xy)
                                self.serial_conn.flush()  # Ensure data is sent instantly
                            # ----------------------------------
                            
                            # Calculate where the robot is looking (flame detection spot)
                            # Distance ahead = 1.0 meters (half of 2.0)
                            target_x = real_x + 1.0 * math.cos(yaw)
                            target_y = real_y + 1.0 * math.sin(yaw)
                            
                            # Calculate heat spot
                            # Distance ahead = 0.33 meters
                            target_heat_x = real_x + 0.33 * math.cos(yaw)
                            target_heat_y = real_y + 0.33 * math.sin(yaw)
                            
                            # Flame Spatial Memory Logic
                            if flame == 1:
                                # Check if this flame is already in memory (within 1 meter)
                                flame_exists = False
                                for f in self.flame_markers_db:
                                    if math.hypot(target_x - f['x'], target_y - f['y']) <= 1.0:
                                        flame_exists = True
                                        break
                                
                                if not flame_exists:
                                    # Register new flame
                                    flame_id = self.next_flame_id
                                    self.next_flame_id += 1
                                    self.flame_markers_db.append({'id': flame_id, 'x': target_x, 'y': target_y})
                                    
                                    marker = Marker()
                                    marker.header.stamp = self.get_clock().now().to_msg()
                                    marker.header.frame_id = "map"
                                    marker.ns = "flame"
                                    marker.id = flame_id
                                    marker.type = Marker.CYLINDER
                                    marker.action = Marker.ADD
                                    marker.pose.position.x = target_x
                                    marker.pose.position.y = target_y
                                    marker.pose.position.z = 0.5
                                    marker.pose.orientation.w = 1.0
                                    marker.scale.x = 0.5
                                    marker.scale.y = 0.5
                                    marker.scale.z = 1.0
                                    marker.color.r = 1.0
                                    marker.color.g = 0.0
                                    marker.color.b = 0.0
                                    marker.color.a = 0.8
                                    marker.lifetime.sec = 0 # Persistent!
                                    self.flame_pub.publish(marker)
                                    self.get_logger().warn(f"🔥 NEW FLAME RECORDED at x={target_x:.2f}, y={target_y:.2f} (ID: {flame_id})")
                            else:
                                # Flame == 0: Verification / Deletion logic
                                # If the robot is looking at a registered flame but sees 0, the fire is out!
                                flames_to_remove = []
                                for i, f in enumerate(self.flame_markers_db):
                                    if math.hypot(target_x - f['x'], target_y - f['y']) <= 1.0:
                                        flames_to_remove.append(i)
                                        
                                        # Delete from RViz
                                        marker = Marker()
                                        marker.header.stamp = self.get_clock().now().to_msg()
                                        marker.header.frame_id = "map"
                                        marker.ns = "flame"
                                        marker.id = f['id']
                                        marker.action = Marker.DELETE
                                        self.flame_pub.publish(marker)
                                        self.get_logger().info(f"✅ FLAME CLEARED at x={f['x']:.2f}, y={f['y']:.2f} (ID: {f['id']})")
                                        
                                # Remove cleared flames from DB (in reverse order to preserve indices)
                                for i in sorted(flames_to_remove, reverse=True):
                                    del self.flame_markers_db[i]
                                
                                
                            # Visualize Temperature Zone (CYLINDER)
                            # Spatial Memory Logic for Temperature
                            if temp >= 34:
                                r, g, b = (1.0, 0.0, 0.0) if temp > 70 else (1.0, 0.5, 0.0)
                                temp_exists = False
                                for f in self.temp_markers_db:
                                    if math.hypot(target_heat_x - f['x'], target_heat_y - f['y']) <= 2.0:
                                        temp_exists = True
                                        # Update existing zone color just in case
                                        marker = self.generate_cloud_marker("map", "temp_cloud", f['id'], r, g, b, 0.5, f['x'], f['y'], 0.2)
                                        self.temp_cloud_pub.publish(marker)
                                        break
                                
                                if not temp_exists:
                                    tid = self.next_temp_id
                                    self.next_temp_id += 1
                                    self.temp_markers_db.append({'id': tid, 'x': target_heat_x, 'y': target_heat_y})
                                    marker = self.generate_cloud_marker("map", "temp_cloud", tid, r, g, b, 0.5, target_heat_x, target_heat_y, 0.2)
                                    self.temp_cloud_pub.publish(marker)
                                    self.get_logger().warn(f"🌡️ HAZARD ZONE: High Temp {temp}C recorded at x={target_heat_x:.2f}, y={target_heat_y:.2f}")
                            else:
                                # Temp < 34: Clear hazards near the robot
                                temps_to_remove = []
                                for i, f in enumerate(self.temp_markers_db):
                                    if math.hypot(target_heat_x - f['x'], target_heat_y - f['y']) <= 2.0:
                                        temps_to_remove.append(i)
                                        marker = Marker()
                                        marker.header.stamp = self.get_clock().now().to_msg()
                                        marker.header.frame_id = "map"
                                        marker.ns = "temp_cloud"
                                        marker.id = f['id']
                                        marker.action = Marker.DELETE
                                        self.temp_cloud_pub.publish(marker)
                                        self.get_logger().info("✅ AREA COOLED: Temp hazard removed.")
                                        
                                for i in sorted(temps_to_remove, reverse=True):
                                    del self.temp_markers_db[i]

                            # Visualize Gas Quality Zone (CYLINDER)
                            # Spatial Memory Logic for Gas
                            if gas_adc >= 650:
                                r, g, b = (0.5, 0.0, 0.5) if gas_adc >= 721 else (0.0, 1.0, 0.0)
                                gas_exists = False
                                for f in self.gas_markers_db:
                                    if math.hypot(real_x - f['x'], real_y - f['y']) <= 2.0:
                                        gas_exists = True
                                        marker = self.generate_cloud_marker("map", "gas_cloud", f['id'], r, g, b, 0.5, f['x'], f['y'], 0.4)
                                        self.gas_cloud_pub.publish(marker)
                                        break
                                
                                if not gas_exists:
                                    gid = self.next_gas_id
                                    self.next_gas_id += 1
                                    self.gas_markers_db.append({'id': gid, 'x': real_x, 'y': real_y})
                                    marker = self.generate_cloud_marker("map", "gas_cloud", gid, r, g, b, 0.5, real_x, real_y, 0.4)
                                    self.gas_cloud_pub.publish(marker)
                                    self.get_logger().warn(f"🌫️ TOXIC GAS DETECTED at x={real_x:.2f}, y={real_y:.2f}")
                            else:
                                # Gas < 650: Clear gas clouds near the robot
                                gas_to_remove = []
                                for i, f in enumerate(self.gas_markers_db):
                                    if math.hypot(real_x - f['x'], real_y - f['y']) <= 2.0:
                                        gas_to_remove.append(i)
                                        marker = Marker()
                                        marker.header.stamp = self.get_clock().now().to_msg()
                                        marker.header.frame_id = "map"
                                        marker.ns = "gas_cloud"
                                        marker.id = f['id']
                                        marker.action = Marker.DELETE
                                        self.gas_cloud_pub.publish(marker)
                                        self.get_logger().info("✅ GAS CLEARED: Area is safe.")
                                        
                                for i in sorted(gas_to_remove, reverse=True):
                                    del self.gas_markers_db[i]
                                    
                            # Spatial Memory Logic for Human Radar
                            human_target_x = real_x + (radar_dist / 100.0) * math.cos(yaw)
                            human_target_y = real_y + (radar_dist / 100.0) * math.sin(yaw)
                            
                            if human == 1:
                                human_exists = False
                                for f in self.human_markers_db:
                                    if math.hypot(human_target_x - f['x'], human_target_y - f['y']) <= 1.5:
                                        human_exists = True
                                        break
                                
                                if not human_exists:
                                    hid = self.next_human_id
                                    self.next_human_id += 1
                                    self.human_markers_db.append({'id': hid, 'x': human_target_x, 'y': human_target_y})
                                    # Cyan cylinder for human
                                    marker = self.generate_cloud_marker("map", "human", hid, 0.0, 1.0, 1.0, 0.8, human_target_x, human_target_y, 0.8)
                                    # Make it tall like a human (1.6m tall, 0.6m wide)
                                    marker.scale.x = 0.6
                                    marker.scale.y = 0.6
                                    marker.scale.z = 1.6
                                    self.human_pub.publish(marker)
                                    self.get_logger().warn(f"🧍 HUMAN DETECTED at x={human_target_x:.2f}, y={human_target_y:.2f} ({radar_dist}cm away)")
                            else:
                                # Human == 0: If robot is within 2.5m of a registered human, assume they left
                                hum_to_remove = []
                                for i, f in enumerate(self.human_markers_db):
                                    if math.hypot(real_x - f['x'], real_y - f['y']) <= 2.5:
                                        hum_to_remove.append(i)
                                        marker = Marker()
                                        marker.header.stamp = self.get_clock().now().to_msg()
                                        marker.header.frame_id = "map"
                                        marker.ns = "human"
                                        marker.id = f['id']
                                        marker.action = Marker.DELETE
                                        self.human_pub.publish(marker)
                                        self.get_logger().info("✅ HUMAN LEFT AREA.")
                                        
                                for i in sorted(hum_to_remove, reverse=True):
                                    del self.human_markers_db[i]
                                
                        except Exception as tf_err:
                            self.get_logger().warn(f"Waiting for SLAM Map... (TF Error: {tf_err})")
                            
                        # Publish other sensor readings (independent of TF map frame)
                        gas_msg = Float32()
                        gas_msg.data = float(gas_adc) * (3.3 / 4095.0)
                        self.gas_pub.publish(gas_msg)
                        
                        radar_dist_msg = Int32()
                        radar_dist_msg.data = int(radar_dist)
                        self.radar_dist_pub.publish(radar_dist_msg)
                        
                        radar_motion_msg = Bool()
                        radar_motion_msg.data = bool(human)
                        self.radar_motion_pub.publish(radar_motion_msg)
                        
                        temp_msg = Float32()
                        temp_msg.data = float(temp)
                        self.temp_pub.publish(temp_msg)
                        
                        # Publish Raw Topics for Cognitive Intervention Node
                        raw_flame_msg = Bool()
                        raw_flame_msg.data = bool(flame)
                        self.raw_flame_pub.publish(raw_flame_msg)
                        
                        raw_gas_msg = Int32()
                        raw_gas_msg.data = int(gas_adc)
                        self.raw_gas_pub.publish(raw_gas_msg)
                        
                        raw_temp_msg = Int32()
                        raw_temp_msg.data = int(temp)
                        self.raw_temp_pub.publish(raw_temp_msg)
                                
                        # Remove processed packet
                        self.buffer = self.buffer[pkt_len:]
                    else:
                        self.buffer.pop(0)
                else:
                    # Not a header, drop first byte and continue searching
                    self.buffer.pop(0)
        except Exception as e:
            self.get_logger().error(f"Serial read error: {e}")

    def generate_cloud_marker(self, frame_id, ns, id, r, g, b, a, pose_x, pose_y, pose_z):
        marker = Marker()
        marker.header.frame_id = frame_id
        # Use rclpy.time.Time() with 0 stamp to avoid TF clock extrapolation errors in RViz
        marker.header.stamp = rclpy.time.Time().to_msg()
        marker.ns = ns
        marker.id = id
        marker.type = Marker.CYLINDER  # CYLINDER is 100% reliable and looks like a solid "zone"
        marker.action = Marker.ADD
        
        marker.pose.position.x = pose_x
        marker.pose.position.y = pose_y
        marker.pose.position.z = pose_z
        marker.pose.orientation.w = 1.0
        
        # Massive cylinder (1.6m diameter, 0.4m height)
        marker.scale.x = 1.6
        marker.scale.y = 1.6
        marker.scale.z = 0.4
        
        marker.color.r = float(r)
        marker.color.g = float(g)
        marker.color.b = float(b)
        marker.color.a = 0.5  # Semi-transparent zone
        
        return marker

def main(args=None):
    rclpy.init(args=args)
    node = WiredSensorsNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
