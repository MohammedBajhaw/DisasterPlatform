import rclpy
from rclpy.node import Node
from visualization_msgs.msg import Marker
from geometry_msgs.msg import Point
from std_msgs.msg import ColorRGBA
import sys
import select
import termios
import tty
import math
import random

class SimulatedMarkersNode(Node):
    def __init__(self):
        super().__init__('simulated_markers_node')
        
        # Publishers for flame markers and gas/dust clouds
        self.flame_pub = self.create_publisher(Marker, '/flame_markers', 10)
        self.gas_pub = self.create_publisher(Marker, '/gas_cloud_markers', 10)
        
        # TF Listener to get robot position
        from tf2_ros import Buffer, TransformListener
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        
        self.flame_id = 1000
        self.gas_id = 2000
        
        # Save terminal settings for non-blocking keyboard read
        self.settings = termios.tcgetattr(sys.stdin)
        
        # Create a timer to poll keyboard inputs (every 0.05 seconds)
        self.timer = self.create_timer(0.05, self.keyboard_poll_callback)
        
        self.get_logger().info("\n======================================================\n"
                               "🎮 simulated_markers_node Started!\n"
                               "Keep this terminal active and use the following keys:\n"
                               "  🔥 Press '1' : Add a Flame Marker (Red Sphere) 1m in front of robot\n"
                               "  ☁️  Press '2' : Add a Dust/Gas Cloud (Semi-transparent particles) 1m in front of robot\n"
                               "  ❌ Press 'q' : Quit\n"
                               "======================================================")

    def get_key(self):
        tty.setraw(sys.stdin.fileno())
        rlist, _, _ = select.select([sys.stdin], [], [], 0.02)
        if rlist:
            key = sys.stdin.read(1)
        else:
            key = ''
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.settings)
        return key

    def keyboard_poll_callback(self):
        key = self.get_key()
        if key == '1':
            self.get_logger().info("🔥 Key '1' pressed! Placing Flame Marker...")
            self.place_flame()
        elif key == '2':
            self.get_logger().info("☁️ Key '2' pressed! Placing Dust/Gas Cloud...")
            self.place_gas_cloud()
        elif key == 'q':
            self.get_logger().warn("Quitting...")
            self.destroy_node()
            rclpy.shutdown()
            sys.exit(0)

    def get_front_coordinates(self, distance=1.0):
        try:
            # Lookup robot position in map
            t = self.tf_buffer.lookup_transform(
                'map',
                'base_link',
                rclpy.time.Time())
            
            rx = t.transform.translation.x
            ry = t.transform.translation.y
            
            # Quaternion to yaw
            q = t.transform.rotation
            siny_cosp = 2 * (q.w * q.z + q.x * q.y)
            cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
            yaw = math.atan2(siny_cosp, cosy_cosp)
            
            # Target position 1m in front
            tx = rx + distance * math.cos(yaw)
            ty = ry + distance * math.sin(yaw)
            return tx, ty, yaw
        except Exception as e:
            self.get_logger().warn(f"Could not get robot pose from TF: {e}")
            return None

    def place_flame(self):
        coords = self.get_front_coordinates(1.0)
        if not coords:
            return
        
        tx, ty, _ = coords
        
        marker = Marker()
        marker.header.frame_id = "map"
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.ns = "flame_markers"
        marker.id = self.flame_id
        marker.type = Marker.SPHERE
        marker.action = Marker.ADD
        
        # Position
        marker.pose.position.x = tx
        marker.pose.position.y = ty
        marker.pose.position.z = 0.15 # raised slightly
        
        # Size (0.3m sphere)
        marker.scale.x = 0.3
        marker.scale.y = 0.3
        marker.scale.z = 0.3
        
        # Color (Vibrant Red)
        marker.color.r = 1.0
        marker.color.g = 0.0
        marker.color.b = 0.0
        marker.color.a = 1.0 # Solid
        
        self.flame_pub.publish(marker)
        self.get_logger().info(f"Planted Flame at ({tx:.2f}, {ty:.2f}) with ID {self.flame_id}")
        self.flame_id += 1

    def place_gas_cloud(self):
        coords = self.get_front_coordinates(1.0)
        if not coords:
            return
        
        tx, ty, _ = coords
        
        marker = Marker()
        marker.header.frame_id = "map"
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.ns = "gas_cloud"
        marker.id = self.gas_id
        marker.type = Marker.SPHERE_LIST
        marker.action = Marker.ADD
        
        # Scale of each individual sphere particle
        marker.scale.x = 0.06
        marker.scale.y = 0.06
        marker.scale.z = 0.06
        
        # We will generate a cloud of 40 random dust particles in a small area
        num_particles = 40
        for _ in range(num_particles):
            p = Point()
            # Random offset inside a sphere of radius 0.25m
            theta = random.uniform(0, 2 * math.pi)
            phi = random.uniform(0, math.pi)
            r = random.uniform(0, 0.25)
            
            p.x = tx + r * math.sin(phi) * math.cos(theta)
            p.y = ty + r * math.sin(phi) * math.sin(theta)
            p.z = 0.05 + r * math.cos(phi) # Keep near the ground
            
            marker.points.append(p)
            
            # Dynamic colors: greyish-yellow/brown dust
            c = ColorRGBA()
            c.r = random.uniform(0.6, 0.8) # grey/yellowish dust
            c.g = random.uniform(0.5, 0.6)
            c.b = random.uniform(0.3, 0.4)
            c.a = random.uniform(0.2, 0.4) # Transparent dust particles
            marker.colors.append(c)
            
        self.gas_pub.publish(marker)
        self.get_logger().info(f"Generated Gas/Dust Cloud at ({tx:.2f}, {ty:.2f}) with ID {self.gas_id}")
        self.gas_id += 1

def main(args=None):
    rclpy.init(args=args)
    node = SimulatedMarkersNode()
    try:
        rclpy.spin(node)
    except SystemExit:
        pass
    except KeyboardInterrupt:
        pass
    finally:
        # Restore terminal settings
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, node.settings)
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
