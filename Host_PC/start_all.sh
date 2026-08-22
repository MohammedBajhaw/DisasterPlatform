#!/bin/bash

# Default IP
DEFAULT_IP="192.168.1.114"

echo "================================================="
echo "   Disaster Platform Automated System Launcher"
echo "================================================="
echo -n "Enter Jetson IP [Default: $DEFAULT_IP]: "
read input_ip

# Use input IP if provided, otherwise fallback to default
JETSON_IP=${input_ip:-$DEFAULT_IP}
JETSON_USER="raitx2"
PASSWORD="1"

echo "Selected Jetson IP: $JETSON_IP"
echo "Launching system tabs..."

# Open first tab (starts the window)
gnome-terminal --title="[HOST] Dashboard" -- bash -c "
  echo 'Starting local Dashboard Server...';
  cd ~/disaster_platform;
  python3 dashboard_server.py;
  exec bash
"

# Open second tab in the same window
gnome-terminal --tab --title="[JETSON] Sensors" -- bash -c "
  echo 'Connecting to Jetson at $JETSON_IP...';
  sshpass -p '$PASSWORD' ssh -o StrictHostKeyChecking=no -t ${JETSON_USER}@${JETSON_IP} \"
    echo '$PASSWORD' | sudo -S docker start my_ros2_robot && \
    echo '$PASSWORD' | sudo -S docker exec my_ros2_robot bash -c 'cd /ros2_ws && source /entrypoint.sh && source install/setup.bash && ros2 run sensor_markers wired_sensors_node'
  \";
  exec bash
"

# Open third tab in the same window
gnome-terminal --tab --title="[JETSON] SLAM" -- bash -c "
  echo 'Connecting to Jetson at $JETSON_IP...';
  sshpass -p '$PASSWORD' ssh -o StrictHostKeyChecking=no -t ${JETSON_USER}@${JETSON_IP} \"
    echo '$PASSWORD' | sudo -S docker start my_ros2_robot && \
    echo '$PASSWORD' | sudo -S docker exec my_ros2_robot bash -c 'cd /ros2_ws && source /entrypoint.sh && source install/setup.bash && ros2 launch disaster_cartographer cartographer.launch.py'
  \";
  exec bash
"

echo "All tabs opened successfully in gnome-terminal!"
