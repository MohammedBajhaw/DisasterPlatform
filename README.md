# Disaster Platform

This repository contains the source code, configurations, and documentation for the Disaster Response Robot platform. The project is split into two major environments: the **Robot (Jetson)** and the **Host PC (Laptop)**.

## Project Structure

```text
DisasterPlatform_Clean/
├── Host_PC/                 # Components to be run on the operator's laptop
│   ├── dashboard_server.py  # Flask/SocketIO telemetry dashboard
│   ├── dashboard_ui/        # Web UI assets
│   ├── rviz/                # RViz visualization configurations
│   ├── host_telemetry.py
│   └── start_all.sh         # Automated launch script for local tabs and SSH sessions
├── Jetson/                  # Components deployed to the robot's NVIDIA Jetson
│   ├── configs/             # SLAM, Nav2, and FastDDS parameters
│   ├── Dockerfile           # Docker image definition for the ROS2 environment
│   ├── ros2_ws/             # The ROS2 Workspace containing custom packages
│   │   └── src/             # Source code for SLAM, mapping, and sensor markers
│   ├── scripts/             # Python orchestration scripts (vision, voice, AI loops)
│   └── models/              # (If applicable) AI models for vision and LLM
├── docs/                    # Project documentation (phases, integration logs)
└── firmware/                # STM32 C/C++ firmware (sensors and LoRa communication)
```

## How to Run the System

The project relies on a Docker container (`my_ros2_robot`) running on the Jetson, orchestrated by a master AI loop, while the operator monitors everything from the Host PC.

### 1. Launching from the Host PC
The easiest way to start the system is using the provided `start_all.sh` script on the laptop. This script automates starting the local dashboard and SSH-ing into the Jetson to launch the ROS2 nodes.

```bash
cd Host_PC/
./start_all.sh
```

### 2. Manual Startup Sequence (Jetson)

If you prefer to start components manually on the Jetson, follow these steps:

#### Step 2a: Start the ROS2 Docker Environment
```bash
# Connect to Jetson
ssh raitx2@10.47.1.35  # (Default password: 1)

# Start the container
docker start my_ros2_robot
```

#### Step 2b: Launch Robot Base and SLAM (Inside Docker)
Open multiple terminals inside the docker container:
```bash
docker exec -it my_ros2_robot bash
source /opt/ros/foxy/setup.bash
source /kobuki_ws/install/setup.bash
ros2 run kobuki_node kobuki_ros_node --ros-args -p device_port:=/dev/kobuki -p base_frame:=base_link -p cmd_vel_timeout:=2.0 --remap /commands/velocity:=/cmd_vel
```
```bash
# In another docker exec terminal:
source /opt/ros/foxy/setup.bash
source install/setup.bash
ros2 launch disaster_cartographer cartographer.launch.py
```
```bash
# In another docker exec terminal:
source /opt/ros/foxy/setup.bash
./start_nav2.sh
```
```bash
# In another docker exec terminal:
source /opt/ros/foxy/setup.bash
source install/setup.bash
ros2 launch explore_lite explore.launch.py
```

#### Step 2c: Launch Custom Sensor Nodes (Inside Docker)
```bash
docker exec -it my_ros2_robot bash
source /opt/ros/foxy/setup.bash
source install/setup.bash
ros2 run sensor_markers wired_sensors_node --ros-args -p serial_port:=/dev/ttyACM1
```
```bash
# In another docker exec terminal:
source /opt/ros/foxy/setup.bash
source install/setup.bash
ros2 run sensor_markers cognitive_intervention_node
```

#### Step 2d: Launch Master AI Loop (Outside Docker, on Jetson Host)
```bash
# Run directly on the Jetson host (not in docker)
python3 ~/disaster_platform/rescue_master_loop.py
```

### 3. Manual Startup Sequence (Host PC)

To monitor the robot from the laptop manually:
```bash
# 1. Start RViz for spatial visualization
ros2 run rviz2 rviz2 -d Host_PC/rviz/nav2_magic.rviz

# 2. Start the telemetry dashboard
cd Host_PC/
python3 dashboard_server.py
```

## Contributing

- Any changes to the ROS2 packages should be made in `Jetson/ros2_ws/src/`.
- Rebuild the workspace inside the Jetson docker container using `colcon build`.
- Make sure not to commit auto-generated `build/`, `install/`, or `log/` directories.
