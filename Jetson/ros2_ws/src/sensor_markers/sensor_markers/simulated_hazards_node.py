#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
import math
import json
import random
from std_msgs.msg import String, Bool, Int32
from nav_msgs.msg import Odometry
from tf2_ros import TransformException
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener

class SimulatedHazardsNode(Node):
    def __init__(self):
        super().__init__('simulated_hazards_node')
        
        # Hazard definitions (Position X, Position Y, Radius, Max Value / Config)
        self.heat_source1 = {'x': 14.0, 'y': 2.3, 'radius': 2.93, 'ambient': 25, 'max_delta': 60}
        self.heat_source2 = {'x': 14.0, 'y': -2.3, 'radius': 2.93, 'ambient': 25, 'max_delta': 60}
        self.flame_source1 = {'x': 2.0, 'y': 1.0, 'radius': 2.0}
        self.flame_source2 = {'x': 8.0, 'y': -1.0, 'radius': 2.0}
        #self.gas_source = {'x': 1.5, 'y': -3.5, 'radius': 3.0, 'baseline': 150, 'max_delta': 1000}
        #self.human_source = {'x': -3.0, 'y': -2.0, 'radius': 2.5}

        # TF listener to get robot pose on the map
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # Publishers for individual sensors
        self.temp_pub = self.create_publisher(Int32, '/sensor/temp', 10)
        self.flame_pub = self.create_publisher(Bool, '/sensor/flame', 10)
        self.gas_pub = self.create_publisher(Int32, '/sensor/gas', 10)
        self.human_pub = self.create_publisher(Bool, '/sensor/human', 10)
        self.radar_pub = self.create_publisher(Int32, '/sensor/radar_dist', 10)

        # Telemetry publisher for the dashboard
        self.telem_pub = self.create_publisher(String, '/robot/telemetry', 10)

        # Timer to update sensors (10Hz)
        self.timer = self.create_timer(0.1, self.update_sensors)

        self.robot_x = 0.0
        self.robot_y = 0.0
        self.get_logger().info("Simulated Hazards Node Initialized.")

    def update_sensors(self):
        # 1. Get current robot pose
        try:
            # We look for map -> base_footprint (TurtleBot3 standard)
            t = self.tf_buffer.lookup_transform('map', 'base_footprint', rclpy.time.Time())
            self.robot_x = t.transform.translation.x
            self.robot_y = t.transform.translation.y
        except TransformException as ex:
            # Fallback to odom if map TF isn't ready
            try:
                t = self.tf_buffer.lookup_transform('odom', 'base_footprint', rclpy.time.Time())
                self.robot_x = t.transform.translation.x
                self.robot_y = t.transform.translation.y
            except TransformException as ex2:
                # Keep last known pose or 0,0
                pass

        # 2. Calculate values based on distance to hazard sources
        
        # Heat calculation (check remaining heat sources)
        dist_heat2 = math.hypot(self.robot_x - self.heat_source2['x'], self.robot_y - self.heat_source2['y'])
        
        temp1 = 25 # Default ambient
        if hasattr(self, 'heat_source1'):
            dist_heat1 = math.hypot(self.robot_x - self.heat_source1['x'], self.robot_y - self.heat_source1['y'])
            temp1 = self.heat_source1['ambient'] + self.heat_source1['max_delta'] * math.exp(-(dist_heat1 / self.heat_source1['radius'])**2)
            
        temp2 = self.heat_source2['ambient'] + self.heat_source2['max_delta'] * math.exp(-(dist_heat2 / self.heat_source2['radius'])**2)
        
        temp_val = int(max(temp1, temp2))
        # Add small fluctuation noise
        temp_val += random.randint(-1, 1)
        temp_val = max(20, min(100, temp_val))

        # Flame calculation (check all active flames)
        dist_flame1 = math.hypot(self.robot_x - self.flame_source1['x'], self.robot_y - self.flame_source1['y'])
        dist_flame2 = math.hypot(self.robot_x - self.flame_source2['x'], self.robot_y - self.flame_source2['y'])
        
        flame_val = (dist_flame1 < self.flame_source1['radius']) or (dist_flame2 < self.flame_source2['radius'])

        # Gas calculation
        if hasattr(self, 'gas_source'):
            dist_gas = math.hypot(self.robot_x - self.gas_source['x'], self.robot_y - self.gas_source['y'])
            gas_val = int(self.gas_source['baseline'] + self.gas_source['max_delta'] * math.exp(-(dist_gas / self.gas_source['radius'])**2))
            # Add noise
            gas_val += random.randint(-15, 15)
            gas_val = max(100, min(4095, gas_val))
        else:
            gas_val = 150

        # Human & Radar calculation
        if hasattr(self, 'human_source'):
            dist_human = math.hypot(self.robot_x - self.human_source['x'], self.robot_y - self.human_source['y'])
            human_val = dist_human < self.human_source['radius']
            radar_dist_val = int(dist_human * 100.0) if human_val else 0
        else:
            human_val = False
            radar_dist_val = 0

        # 3. Publish ROS2 topics
        self.temp_pub.publish(Int32(data=temp_val))
        self.flame_pub.publish(Bool(data=flame_val))
        self.gas_pub.publish(Int32(data=gas_val))
        self.human_pub.publish(Bool(data=human_val))
        self.radar_pub.publish(Int32(data=radar_dist_val))

        # 4. Publish telemetry JSON for dashboard
        telem_data = {
            'x': self.robot_x,
            'y': self.robot_y,
            'flame': flame_val,
            'human': human_val,
            'gas_adc': gas_val,
            'radar_dist': radar_dist_val,
            'temp': temp_val,
            'rssi': -55,  # Simulated stable RSSI
            'packet_count': 0, # Handled by server
            'uptime': 0        # Handled by server
        }
        self.telem_pub.publish(String(data=json.dumps(telem_data)))

def main(args=None):
    rclpy.init(args=args)
    node = SimulatedHazardsNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
