#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data, QoSProfile, ReliabilityPolicy, DurabilityPolicy
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
        
        # USE WIDE-OPEN QoS PROFILES to guarantee connection regardless of Publisher QoS!
        # Best Effort subscriber can connect to Reliable OR Best Effort publishers.
        
        # 1. DIRECT HARDWARE SENSOR SUBSCRIPTIONS
        self.raw_flame_sub = self.create_subscription(Bool, '/sensor/flame', self.raw_flame_callback, qos_profile_sensor_data)
        self.temp_sub = self.create_subscription(Int32, '/sensor/temp', self.temp_callback, qos_profile_sensor_data)
        
        # 2. SPATIAL MARKER SUBSCRIPTIONS (Try both Best Effort and Reliable profiles)
        best_effort_qos = qos_profile_sensor_data
        reliable_transient_qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        
        self.flame_sub1 = self.create_subscription(Marker, '/local_flame_marker', self.flame_marker_callback, best_effort_qos)
        self.flame_sub2 = self.create_subscription(Marker, '/local_flame_marker', self.flame_marker_callback, reliable_transient_qos)
        self.flame_sub3 = self.create_subscription(Marker, '/local_flame_marker', self.flame_marker_callback, 10) # Default Reliable
        
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
        self.cloud_timer = self.create_timer(0.5, self.publish_hazard_cloud)
        self.heartbeat_timer = self.create_timer(5.0, self.heartbeat_tick)

        self.get_logger().info("=== Cognitive MUX Node Active: BULLETPROOF QoS ENABLED ===")

    def heartbeat_tick(self):
        self.get_logger().info("❤️ Guard Node is active and listening for hazards...")

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
            return

        self.is_recovering = True
        self.reaction_type = reaction_type
        self.recovery_end_time = now + 2.0  # 2.0s duration (~20cm backup)
        self.current_speed = 0.0  # Start at 0 m/s for smooth acceleration

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
            if self.current_speed > target_speed:
                self.current_speed = max(target_speed, self.current_speed - 0.01)
                
            twist = Twist()
            twist.linear.x = self.current_speed
            twist.angular.z = 0.0
            self.cmd_vel_pub.publish(twist)
        else:
            stop_cmd = Twist()
            self.cmd_vel_pub.publish(stop_cmd)
            self.is_recovering = False
            self.recovery_cooldown_until = now + 4.0
            self.get_logger().info("🛑 Evasion maneuver complete. Control returned to Nav2.")

    def raw_flame_callback(self, msg):
        if msg.data:
            self.get_logger().warn("🔥 RAW HARDWARE FLAME SENSOR HIGH (/sensor/flame = True)!")
            self.start_backup('flame')

    def temp_callback(self, msg):
        if msg.data >= 34:  # Restored to 34°C (Normal room temp is 31°C)
            self.get_logger().warn(f"🔥 HIGH TEMP SENSOR: {msg.data}°C!")
            self.start_backup('heat')

    def flame_marker_callback(self, msg):
        if msg.action == Marker.ADD:
            self.get_logger().warn(f"🔥 SPATIAL FLAME MARKER RECEIVED at ({msg.pose.position.x:.2f}, {msg.pose.position.y:.2f})")
            self.start_backup('flame')

    def publish_hazard_cloud(self):
        pass # Disabled temporarily to focus purely on evasion stability

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
