import rclpy
from rclpy.node import Node
import serial
import struct
import math
from geometry_msgs.msg import PointStamped
from tf2_ros import Buffer, TransformListener

class LoraTxNode(Node):
    def __init__(self):
        super().__init__('lora_tx_node')
        
        # Parameters for UART connection to STM32F4 Black Pill
        self.declare_parameter('serial_port', '/dev/ttyACM0')
        self.declare_parameter('baud_rate', 115200)
        
        port = self.get_parameter('serial_port').value
        baud = self.get_parameter('baud_rate').value
        
        try:
            self.serial_conn = serial.Serial(port, baud, timeout=1)
            self.get_logger().info(f"Connected to STM32F4 on {port} at {baud} baud for LoRa TX.")
        except Exception as e:
            self.serial_conn = None
            self.get_logger().error(f"Failed to connect to STM32F4: {e}")
            
        # TF Listener for robot pose
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        
        # Subscription to flame points
        self.flame_detected = False
        self.subscription = self.create_subscription(
            PointStamped,
            '/flame_points',
            self.flame_callback,
            10)
            
        # Timer to send telemetry at 1 Hz (LoRa is low bandwidth)
        self.timer = self.create_timer(1.0, self.send_telemetry)
        
    def flame_callback(self, msg):
        self.flame_detected = True
        self.get_logger().info("Flame flag set for next LoRa transmission!")
        
    def send_telemetry(self):
        if self.serial_conn is None:
            return
            
        robot_x = 0.0
        robot_y = 0.0
        
        try:
            t = self.tf_buffer.lookup_transform('map', 'base_link', rclpy.time.Time())
            robot_x = t.transform.translation.x
            robot_y = t.transform.translation.y
        except Exception as e:
            # If no TF, we send 0.0 (or last known)
            pass
            
        # Structure: 
        # [0xAB, 0xCD] (Header)
        # [4 bytes float X]
        # [4 bytes float Y]
        # [1 byte bool Flame]
        # [1 byte Checksum]
        # Total: 12 bytes
        
        flame_val = 1 if self.flame_detected else 0
        
        # Pack floats into bytes (little-endian)
        payload = struct.pack('<ffB', robot_x, robot_y, flame_val)
        
        # Calculate simple XOR checksum
        checksum = 0
        for b in payload:
            checksum ^= b
            
        # Final packet
        packet = bytes([0xAB, 0xCD]) + payload + bytes([checksum])
        
        try:
            self.serial_conn.write(packet)
            self.get_logger().debug(f"Sent LoRa Packet: X={robot_x:.2f}, Y={robot_y:.2f}, Flame={flame_val}")
        except Exception as e:
            self.get_logger().error(f"Serial write error: {e}")
            
        # Reset flame flag after sending
        self.flame_detected = False

def main(args=None):
    rclpy.init(args=args)
    node = LoraTxNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
