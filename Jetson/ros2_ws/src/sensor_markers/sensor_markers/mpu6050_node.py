#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
import os
import fcntl
import struct
import math
from sensor_msgs.msg import Imu
from geometry_msgs.msg import Quaternion

# Linux I2C ioctl constant
I2C_SLAVE = 0x0703

# MPU6050 Registers
MPU6050_ADDR = 0x68
REG_PWR_MGMT_1 = 0x6B
REG_GYRO_CONFIG = 0x1B
REG_ACCEL_CONFIG = 0x1C
REG_FIFO_EN = 0x23
REG_INT_ENABLE = 0x38
REG_ACCEL_XOUT_H = 0x3B

class Mpu6050Node(Node):
    def __init__(self):
        super().__init__('mpu6050_node')
        
        self.declare_parameter('i2c_bus', '/dev/i2c-1')
        self.declare_parameter('i2c_address', 0x68)
        self.declare_parameter('frame_id', 'imu_link')
        self.declare_parameter('publish_rate', 100.0) # Hz
        
        self.bus_path = self.get_parameter('i2c_bus').value
        self.addr = self.get_parameter('i2c_address').value
        self.frame_id = self.get_parameter('frame_id').value
        publish_rate = self.get_parameter('publish_rate').value
        
        # ROS2 Publisher
        self.imu_pub = self.create_publisher(Imu, '/imu', 10)
        
        # State variables for Complementary Filter
        self.roll = 0.0
        self.pitch = 0.0
        self.yaw = 0.0
        self.last_time = self.get_clock().now()
        
        # Initialize I2C connection
        self.fd = None
        if self.init_sensor():
            self.get_logger().info(f"MPU6050 IMU initialized on {self.bus_path} at address {hex(self.addr)}")
            timer_period = 1.0 / publish_rate
            self.timer = self.create_timer(timer_period, self.timer_callback)
        else:
            self.get_logger().error(f"Failed to initialize MPU6050 on {self.bus_path}")

    def init_sensor(self):
        try:
            # Open I2C device
            self.fd = os.open(self.bus_path, os.O_RDWR)
            # Set I2C slave address
            fcntl.ioctl(self.fd, I2C_SLAVE, self.addr)
            
            # Wake up MPU6050 (write 0 to PWR_MGMT_1)
            os.write(self.fd, bytes([REG_PWR_MGMT_1, 0]))
            
            # Set Gyro range to +/- 250 deg/s (write 0 to GYRO_CONFIG)
            os.write(self.fd, bytes([REG_GYRO_CONFIG, 0]))
            
            # Set Accel range to +/- 2g (write 0 to ACCEL_CONFIG)
            os.write(self.fd, bytes([REG_ACCEL_CONFIG, 0]))
            
            return True
        except Exception as e:
            self.get_logger().error(f"I2C initialization error: {e}")
            if self.fd is not None:
                os.close(self.fd)
                self.fd = None
            return False

    def read_raw_data(self):
        if self.fd is None:
            return None
        try:
            # Point to ACCEL_XOUT_H register
            os.write(self.fd, bytes([REG_ACCEL_XOUT_H]))
            # Read 14 bytes (accel_x, accel_y, accel_z, temp, gyro_x, gyro_y, gyro_z)
            data = os.read(self.fd, 14)
            if len(data) == 14:
                return struct.unpack('>hhhhhhh', data)
        except Exception as e:
            self.get_logger().error(f"I2C read error: {e}")
        return None

    def timer_callback(self):
        raw_vals = self.read_raw_data()
        if raw_vals is None:
            return
            
        ax, ay, az, temp, gx, gy, gz = raw_vals
        
        # Conversion factors
        # +/- 2g sensitivity: 16384 LSB/g
        # Convert to m/s^2 (1 g = 9.80665 m/s^2)
        accel_factor = 9.80665 / 16384.0
        ax_phys = ax * accel_factor
        ay_phys = ay * accel_factor
        az_phys = az * accel_factor
        
        # +/- 250 deg/s sensitivity: 131 LSB/(deg/s)
        # Convert to rad/s (1 deg = pi/180 rad)
        gyro_factor = (math.pi / 180.0) / 131.0
        gx_phys = gx * gyro_factor
        gy_phys = gy * gyro_factor
        gz_phys = gz * gyro_factor
        
        # Time delta
        current_time = self.get_clock().now()
        dt = (current_time - self.last_time).nanoseconds / 1e9
        self.last_time = current_time
        
        # Complementary Filter for orientation estimation
        # Pitch and Roll from accelerometer
        # Note: using signs based on standard NED/ENU robot conventions
        try:
            accel_pitch = math.atan2(-ax_phys, math.sqrt(ay_phys**2 + az_phys**2))
            accel_roll = math.atan2(ay_phys, az_phys)
        except ZeroDivisionError:
            accel_pitch = 0.0
            accel_roll = 0.0
            
        # Integrate gyro data
        # filter weight: 0.98 for gyro (integration), 0.02 for accelerometer (absolute reference)
        self.roll = 0.98 * (self.roll + gx_phys * dt) + 0.02 * accel_roll
        self.pitch = 0.98 * (self.pitch + gy_phys * dt) + 0.02 * accel_pitch
        self.yaw += gz_phys * dt # Integrate yaw directly (subject to drift, but standard for 6-DOF IMUs)
        
        # Roll, Pitch, Yaw to Quaternion
        cy = math.cos(self.yaw * 0.5)
        sy = math.sin(self.yaw * 0.5)
        cp = math.cos(self.pitch * 0.5)
        sp = math.sin(self.pitch * 0.5)
        cr = math.cos(self.roll * 0.5)
        sr = math.sin(self.roll * 0.5)
        
        qw = cr * cp * cy + sr * sp * sy
        qx = sr * cp * cy - cr * sp * sy
        qy = cr * sp * cy + sr * cp * sy
        qz = cr * cp * sy - sr * sp * cy
        
        # Build IMU message
        msg = Imu()
        msg.header.stamp = current_time.to_msg()
        msg.header.frame_id = self.frame_id
        
        # Orientation
        msg.orientation.w = qw
        msg.orientation.x = qx
        msg.orientation.y = qy
        msg.orientation.z = qz
        
        # Angular Velocity
        msg.angular_velocity.x = gx_phys
        msg.angular_velocity.y = gy_phys
        msg.angular_velocity.z = gz_phys
        
        # Linear Acceleration
        msg.linear_acceleration.x = ax_phys
        msg.linear_acceleration.y = ay_phys
        msg.linear_acceleration.z = az_phys
        
        # Set covariances (reasonable values for MPU6050)
        msg.orientation_covariance = [
            0.0025, 0.0, 0.0,
            0.0, 0.0025, 0.0,
            0.0, 0.0, 0.0025
        ]
        msg.angular_velocity_covariance = [
            0.0001, 0.0, 0.0,
            0.0, 0.0001, 0.0,
            0.0, 0.0, 0.0001
        ]
        msg.linear_acceleration_covariance = [
            0.01, 0.0, 0.0,
            0.0, 0.01, 0.0,
            0.0, 0.0, 0.01
        ]
        
        self.imu_pub.publish(msg)

    def __del__(self):
        if self.fd is not None:
            os.close(self.fd)

def main(args=None):
    rclpy.init(args=args)
    node = Mpu6050Node()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
