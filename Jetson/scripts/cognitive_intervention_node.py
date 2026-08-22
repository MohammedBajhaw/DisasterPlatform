#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
import math
import struct
from std_msgs.msg import Bool, Int32
from visualization_msgs.msg import Marker
from geometry_msgs.msg import Twist
from sensor_msgs.msg import PointCloud2, PointField
from tf2_ros import TransformException
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener

class CognitiveInterventionNode(Node):
    def __init__(self):
        super().__init__('cognitive_intervention_node')
        
        # 1. DIRECT HARDWARE SENSOR SUBSCRIPTIONS (from wired_sensors_node)
        self.raw_flame_sub = self.create_subscription(Bool, '/sensor/flame', self.raw_flame_callback, 10)
        self.temp_sub = self.create_subscription(Int32, '/sensor/temp', self.temp_callback, 10)
        self.gas_sub = self.create_subscription(Int32, '/sensor/gas', self.gas_callback, 10)

        # 2. SPATIAL MARKER SUBSCRIPTIONS
        self.flame_sub1 = self.create_subscription(Marker, '/local_flame_marker', self.flame_marker_callback, 10)
        self.flame_sub2 = self.create_subscription(Marker, '/flame_markers', self.flame_marker_callback, 10)

        # 3. MUX ARCHITECTURE: Intercept Nav2 velocity on /cmd_vel_nav2
        self.nav2_sub = self.create_subscription(Twist, '/cmd_vel_nav2', self.nav2_callback, 10)
        
        # 4. OUTPUT PUBLISHERS (Publish directly to Kobuki robot base on /cmd_vel)
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.cloud_pub = self.create_publisher(PointCloud2, '/hazard_keepout_points', 10)

        # TF listener for robot pose on map
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        
        # State Variables
        self.hazard_zones = []  # list of (x, y, yaw, type)
        self.is_recovering = False
        self.recovery_end_time = 0.0
        self.recovery_cooldown_until = 0.0
        self.current_speed = 0.0
        self.reaction_type = 'flame'

        # 20 Hz Control Loop for MUX velocity routing & smooth motion
        self.control_timer = self.create_timer(0.05, self.control_tick)
        
        # 2 Hz Timer to publish keepout pointcloud to Nav2 costmap
        self.cloud_timer = self.create_timer(0.5, self.publish_hazard_cloud)

        self.get_logger().info("=== Cognitive MUX Node Active: Guarding Robot via /sensor/flame & MUX ===")

    def nav2_callback(self, msg):
        """Pass-through Nav2 velocity commands ONLY when no emergency intervention is active."""
        if not self.is_recovering:
            self.cmd_vel_pub.publish(msg)

    def get_robot_pose(self):
        try:
            t = self.tf_buffer.lookup_transform('map', 'base_link', rclpy.time.Time())
            rx = t.transform.translation.x
            ry = t.transform.translation.y
            q = t.transform.rotation
            siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
            cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
            yaw = math.atan2(siny_cosp, cosy_cosp)
            return rx, ry, yaw
        except TransformException:
            return None

    def start_backup(self, reaction_type='flame'):
        now = self.get_clock().now().nanoseconds / 1e9
        if self.is_recovering:
            return
        if now < self.recovery_cooldown_until:
            self.get_logger().info(f"Cooldown active ({self.recovery_cooldown_until - now:.1f}s remaining).")
            return

        self.is_recovering = True
        self.reaction_type = reaction_type
        self.recovery_end_time = now + 2.0  # 2.0s duration (~20cm backup)
        self.current_speed = 0.0  # Start at 0 m/s for smooth acceleration

        # Stop forward motion immediately
        stop_cmd = Twist()
        self.cmd_vel_pub.publish(stop_cmd)

        self.get_logger().warn(f"🚨 HAZARD EMERGENCY! {reaction_type.upper()} DETECTED! OVERRIDING NAV2 & REVERSING NOW!")

    def control_tick(self):
        """Executes controlled, non-oscillating backup velocity ramping."""
        if not self.is_recovering:
            return
        
        now = self.get_clock().now().nanoseconds / 1e9
        if now < self.recovery_end_time:
            target_speed = -0.08  # Safe, smooth reverse speed
            
            # Smooth acceleration (0.01 m/s per tick at 20Hz)
            if self.current_speed > target_speed:
                self.current_speed = max(target_speed, self.current_speed - 0.01)
                
            twist = Twist()
            twist.linear.x = self.current_speed
            twist.angular.z = 0.0
            self.cmd_vel_pub.publish(twist)
        else:
            # Emergency backing up finished -> Stop cleanly
            stop_cmd = Twist()
            self.cmd_vel_pub.publish(stop_cmd)
            
            self.is_recovering = False
            self.recovery_cooldown_until = now + 4.0  # 4 seconds cooldown
            self.get_logger().info("🛑 Evasion maneuver complete. Control returned to Nav2.")

    def raw_flame_callback(self, msg):
        """Direct 20Hz hardware flame sensor callback from STM32 / wired_sensors_node."""
        if msg.data:  # True = Flame sensor active!
            self.get_logger().warn("🔥 RAW HARDWARE FLAME SENSOR HIGH (/sensor/flame = True)!")
            
            # Add hazard circle to map pose if pose is available
            pose = self.get_robot_pose()
            if pose:
                rx, ry, yaw = pose
                hx = rx + 1.0 * math.cos(yaw)
                hy = ry + 1.0 * math.sin(yaw)
                spam = any(hz[3] == 'flame' and math.hypot(hx - hz[0], hy - hz[1]) < 1.0 for hz in self.hazard_zones)
                if not spam:
                    self.hazard_zones.append((hx, hy, 0.0, 'flame'))
                    self.get_logger().warn(f"📍 Registered Flame Hazard Circle at ({hx:.2f}, {hy:.2f})")
            
            self.start_backup('flame')

    def temp_callback(self, msg):
        if msg.data >= 32:  # Adjusted to 32°C matching sensor telemetry
            self.get_logger().warn(f"🔥 HIGH TEMP SENSOR: {msg.data}°C!")
            pose = self.get_robot_pose()
            if pose:
                rx, ry, yaw = pose
                hx = rx + 0.33 * math.cos(yaw)
                hy = ry + 0.33 * math.sin(yaw)
                spam = any(hz[3] == 'heat' and math.hypot(hx - hz[0], hy - hz[1]) < 1.0 for hz in self.hazard_zones)
                if not spam:
                    self.hazard_zones.append((hx, hy, yaw, 'heat'))
            self.start_backup('heat')

    def gas_callback(self, msg):
        pass

    def flame_marker_callback(self, msg):
        if msg.action == Marker.ADD:
            self.get_logger().warn(f"🔥 SPATIAL FLAME MARKER RECEIVED at ({msg.pose.position.x:.2f}, {msg.pose.position.y:.2f})")
            hx = msg.pose.position.x
            hy = msg.pose.position.y
            spam = any(hz[3] == 'flame' and math.hypot(hx - hz[0], hy - hz[1]) < 1.0 for hz in self.hazard_zones)
            if not spam:
                self.hazard_zones.append((hx, hy, 0.0, 'flame'))
            self.start_backup('flame')
        elif msg.action == Marker.DELETE:
            hx = msg.pose.position.x
            hy = msg.pose.position.y
            self.hazard_zones = [hz for hz in self.hazard_zones if not (hz[3] == 'flame' and math.hypot(hx - hz[0], hy - hz[1]) < 1.0)]

    def publish_hazard_cloud(self):
        if not self.hazard_zones:
            return

        points = []
        radius = 0.35
        step = 0.05
        
        for hz in self.hazard_zones:
            hx, hy = hz[0], hz[1]
            pz = 0.5
            for dx_idx in range(int(-radius/step), int(radius/step)+1):
                for dy_idx in range(int(-radius/step), int(radius/step)+1):
                    dx = dx_idx * step
                    dy = dy_idx * step
                    if dx*dx + dy*dy <= radius*radius:
                        points.append((hx + dx, hy + dy, pz))

        msg = PointCloud2()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'
        msg.height = 1
        msg.width = len(points)
        msg.is_dense = True
        msg.is_bigendian = False

        msg.fields = [
            PointField(name='x', offset=0, datatype=PointField.FLOAT32, count=1),
            PointField(name='y', offset=4, datatype=PointField.FLOAT32, count=1),
            PointField(name='z', offset=8, datatype=PointField.FLOAT32, count=1)
        ]
        
        msg.point_step = 12
        msg.row_step = msg.point_step * msg.width
        
        buffer = bytearray()
        for p in points:
            buffer.extend(struct.pack('<fff', p[0], p[1], p[2]))
            
        msg.data = bytes(buffer)
        self.cloud_pub.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = CognitiveInterventionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
