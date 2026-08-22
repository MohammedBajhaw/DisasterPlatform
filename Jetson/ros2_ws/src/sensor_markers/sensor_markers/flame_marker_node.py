import rclpy
from rclpy.node import Node
from visualization_msgs.msg import Marker
from geometry_msgs.msg import Point
import serial
import threading
import math

class FlameMarkerNode(Node):
    def __init__(self):
        super().__init__('flame_marker_node')
        
        # Publisher for the points to avoid Foxy/Humble incompatibilities
        from geometry_msgs.msg import PointStamped
        self.point_pub = self.create_publisher(PointStamped, '/flame_points', 10)
        
        # Parameters for serial port
        self.declare_parameter('serial_port', '/dev/ttyUSB1')
        self.declare_parameter('baud_rate', 115200)
        self.declare_parameter('flame_active_value', '0')
        
        port = self.get_parameter('serial_port').value
        baud = self.get_parameter('baud_rate').value
        self.flame_active_val = self.get_parameter('flame_active_value').value
        
        self.last_publish_time = 0.0 # to store the epoch time of last publish
        
        # TF Listener to get robot position in map
        from tf2_ros import Buffer, TransformListener
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # Try to connect to serial port
        try:
            self.serial_conn = serial.Serial(port, baud, timeout=1)
            self.get_logger().info(f"Connected to {port} at {baud} baud.")
            
            # Start a thread to read serial data continuously
            self.read_thread = threading.Thread(target=self.serial_read_loop)
            self.read_thread.daemon = True
            self.read_thread.start()
        except Exception as e:
            self.get_logger().error(f"Failed to connect to serial port {port}: {e}")
            self.get_logger().warn("Running in simulation mode (No serial data). Use topic to trigger manually if needed.")


    def serial_read_loop(self):
        import time
        while rclpy.ok():
            if self.serial_conn.in_waiting > 0:
                try:
                    line = self.serial_conn.readline().decode('utf-8').strip()
                    if line.startswith("FLAME:"):
                        val = line.split(":")[1]
                        if val == self.flame_active_val:
                            # Rate limit: Only publish once every 2.0 seconds
                            now = time.time()
                            if now - self.last_publish_time > 2.0:
                                self.last_publish_time = now
                                self.get_logger().warn("🔥 FLAME DETECTED! Placing marker...")
                                self.place_flame_marker()
                except Exception as e:
                    self.get_logger().error(f"Error reading serial: {e}")

    def place_flame_marker(self):
        try:
            # Look up the transform from map to base_link
            t = self.tf_buffer.lookup_transform(
                'map',
                'base_link',
                rclpy.time.Time())

            rx = t.transform.translation.x
            ry = t.transform.translation.y
            
            q = t.transform.rotation
            siny_cosp = 2 * (q.w * q.z + q.x * q.y)
            cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
            yaw = math.atan2(siny_cosp, cosy_cosp)

            distance_ahead = 0.5
            marker_x = rx + distance_ahead * math.cos(yaw)
            marker_y = ry + distance_ahead * math.sin(yaw)

            # Publish as PointStamped instead of Marker to avoid Foxy/Humble struct mismatch
            from geometry_msgs.msg import PointStamped
            pt = PointStamped()
            pt.header.frame_id = "map"
            pt.header.stamp = rclpy.time.Time().to_msg()
            pt.point.x = marker_x
            pt.point.y = marker_y
            pt.point.z = 0.5
            
            self.point_pub.publish(pt)
            self.get_logger().info(f"Published flame point at x: {marker_x:.2f}, y: {marker_y:.2f}")

        except Exception as e:
            self.get_logger().error(f"Could not transform map to base_link: {e}")

def main(args=None):
    rclpy.init(args=args)
    node = FlameMarkerNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
