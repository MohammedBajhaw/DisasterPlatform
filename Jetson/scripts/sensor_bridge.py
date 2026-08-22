#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PointStamped, PoseStamped
from visualization_msgs.msg import Marker, MarkerArray
from std_msgs.msg import Float32

class SensorVisualizerNode(Node):
    def __init__(self):
        super().__init__('sensor_visualizer_node')
        
        # Subscribe to sensor data from Jetson
        self.flame_sub = self.create_subscription(PointStamped, '/flame_points', self.flame_callback, 10)
        self.pose_sub = self.create_subscription(PoseStamped, '/lora/robot_pose', self.pose_callback, 10)
        self.temp_sub = self.create_subscription(Float32, '/sensor/temperature', self.temp_callback, 10)
        self.gas_sub = self.create_subscription(Float32, '/sensor/gas_voltage', self.gas_callback, 10)
            
        # Publish Humble-compatible Markers locally to RViz
        self.flame_pub = self.create_publisher(Marker, '/local_flame_marker', 10)
        self.temp_pub = self.create_publisher(Marker, '/local_temp_cloud', 10)
        self.gas_pub = self.create_publisher(Marker, '/local_gas_cloud', 10)
        
        self.current_pose = None
        
        self.get_logger().info('Local Humble Sensor Visualizer is running...')

    def pose_callback(self, msg):
        self.current_pose = msg

    def flame_callback(self, msg):
        self.get_logger().info(f"Local Flame received at x={msg.point.x:.2f}, y={msg.point.y:.2f}")
        
        marker = Marker()
        marker.header = msg.header
        marker.ns = "flame"
        marker.id = 0
        marker.type = Marker.CYLINDER
        marker.action = Marker.ADD
        
        marker.pose.position.x = msg.point.x
        marker.pose.position.y = msg.point.y
        marker.pose.position.z = msg.point.z
        marker.pose.orientation.w = 1.0
        
        # A medium-sized flame indicator
        marker.scale.x = 0.5
        marker.scale.y = 0.5
        marker.scale.z = 1.0
        
        marker.color.r = 1.0
        marker.color.g = 0.0
        marker.color.b = 0.0
        marker.color.a = 0.8
        
        marker.lifetime.sec = 5 # Disappear after 5 seconds instead of staying forever
        
        self.flame_pub.publish(marker)

    def generate_zone_marker(self, frame_id, ns, id, r, g, b, a, pose, z_offset):
        marker = Marker()
        marker.header.frame_id = frame_id
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.ns = ns
        marker.id = id
        marker.type = Marker.CYLINDER
        marker.action = Marker.ADD
        
        marker.pose.position.x = pose.pose.position.x
        marker.pose.position.y = pose.pose.position.y
        marker.pose.position.z = z_offset
        marker.pose.orientation.w = 1.0
        
        # Massive 1.6m zone
        marker.scale.x = 1.6
        marker.scale.y = 1.6
        marker.scale.z = 0.4
        
        marker.color.r = float(r)
        marker.color.g = float(g)
        marker.color.b = float(b)
        marker.color.a = float(a)
        
        return marker

    def temp_callback(self, msg):
        if self.current_pose is None:
            return
            
        temp = msg.data
        if temp >= 40:
            r, g, b = (1.0, 0.0, 0.0) if temp > 70 else (1.0, 0.5, 0.0)
            marker = self.generate_zone_marker("map", "temp_zone", 0, r, g, b, 0.5, self.current_pose, 0.2)
            self.temp_pub.publish(marker)
        else:
            delete_marker = Marker()
            delete_marker.action = Marker.DELETE
            delete_marker.ns = "temp_zone"
            delete_marker.id = 0
            self.temp_pub.publish(delete_marker)

    def gas_callback(self, msg):
        if self.current_pose is None:
            return
            
        # Convert voltage back to ADC roughly to match thresholds
        gas_adc = (msg.data / 3.3) * 4095.0
        
        if gas_adc >= 650:
            r, g, b = (0.5, 0.0, 0.5) if gas_adc >= 721 else (0.0, 1.0, 0.0)
            marker = self.generate_zone_marker("map", "gas_zone", 1, r, g, b, 0.5, self.current_pose, 0.4)
            self.gas_pub.publish(marker)
        else:
            delete_marker = Marker()
            delete_marker.action = Marker.DELETE
            delete_marker.ns = "gas_zone"
            delete_marker.id = 1
            self.gas_pub.publish(delete_marker)

def main(args=None):
    rclpy.init(args=args)
    node = SensorVisualizerNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
