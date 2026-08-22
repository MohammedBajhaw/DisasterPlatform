#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
import time

try:
    from smbus2 import SMBus
except ImportError:
    print("smbus2 not found. Please install using: pip3 install smbus2")
    SMBus = None

class Bno055Node(Node):
    def __init__(self):
        super().__init__('bno055_node')
        
        self.declare_parameter('i2c_bus', 1)
        self.declare_parameter('i2c_addr', 0x28)
        self.declare_parameter('frame_id', 'imu_link')
        
        self.bus_num = self.get_parameter('i2c_bus').value
        self.address = self.get_parameter('i2c_addr').value
        self.frame_id = self.get_parameter('frame_id').value
        
        self.imu_pub = self.create_publisher(Imu, '/imu/data', 50)
        
        if SMBus is None:
            self.get_logger().error("smbus2 library is missing! Node cannot start.")
            return

        try:
            self.bus = SMBus(self.bus_num)
            self.get_logger().info(f"Connected to I2C bus {self.bus_num}")
            
            # Reset BNO055
            self.bus.write_byte_data(self.address, 0x3F, 0x20)
            time.sleep(0.65)
            
            # Set to Normal power mode
            self.bus.write_byte_data(self.address, 0x3E, 0x00)
            time.sleep(0.05)
            
            # Set to IMU mode (Sensor Fusion without Magnetometer)
            # This is critical for indoor SLAM to prevent magnetic interference snapping
            self.bus.write_byte_data(self.address, 0x3D, 0x08)
            time.sleep(0.05)
            
            self.get_logger().info(f"BNO055 Initialized on address 0x{self.address:02X} in IMU mode (No Mag).")
        except Exception as e:
            self.get_logger().error(f"Failed to initialize BNO055: {e}")
            self.bus = None

        # Publish IMU data at 50 Hz
        self.timer = self.create_timer(0.02, self.publish_imu)

    def publish_imu(self):
        if self.bus is None:
            return
            
        try:
            # Read 8 bytes starting from Quaternions register (0x20)
            data = self.bus.read_i2c_block_data(self.address, 0x20, 8)
            
            qw = int.from_bytes(data[0:2], byteorder='little', signed=True)
            qx = int.from_bytes(data[2:4], byteorder='little', signed=True)
            qy = int.from_bytes(data[4:6], byteorder='little', signed=True)
            qz = int.from_bytes(data[6:8], byteorder='little', signed=True)
            
            # Scale for Quaternions in BNO055 is 1 LSB = 1/16384.0
            scale = 16384.0
            
            # Read Raw Accelerometer (0x08) 6 bytes (MUST include Gravity for Cartographer!)
            accel_data = self.bus.read_i2c_block_data(self.address, 0x08, 6)
            ax = int.from_bytes(accel_data[0:2], byteorder='little', signed=True)
            ay = int.from_bytes(accel_data[2:4], byteorder='little', signed=True)
            az = int.from_bytes(accel_data[4:6], byteorder='little', signed=True)
            accel_scale = 100.0 # m/s^2 scale is 100 LSB = 1m/s^2
            
            # Read Angular Velocity (0x14) 6 bytes
            gyro_data = self.bus.read_i2c_block_data(self.address, 0x14, 6)
            gx = int.from_bytes(gyro_data[0:2], byteorder='little', signed=True)
            gy = int.from_bytes(gyro_data[2:4], byteorder='little', signed=True)
            gz = int.from_bytes(gyro_data[4:6], byteorder='little', signed=True)
            gyro_scale = 16.0 # dps scale, needs conversion to rad/s
            deg_to_rad = 3.14159265359 / 180.0
            
            msg = Imu()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = self.frame_id
            
            msg.orientation.w = qw / scale
            msg.orientation.x = qx / scale
            msg.orientation.y = qy / scale
            msg.orientation.z = qz / scale
            
            msg.linear_acceleration.x = ax / accel_scale
            msg.linear_acceleration.y = ay / accel_scale
            msg.linear_acceleration.z = az / accel_scale
            
            msg.angular_velocity.x = (gx / gyro_scale) * deg_to_rad
            msg.angular_velocity.y = (gy / gyro_scale) * deg_to_rad
            msg.angular_velocity.z = (gz / gyro_scale) * deg_to_rad
            
            self.imu_pub.publish(msg)
            
        except OSError as e:
            self.get_logger().warning(f"I2C Read Error: {e}")

def main(args=None):
    rclpy.init(args=args)
    node = Bno055Node()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
