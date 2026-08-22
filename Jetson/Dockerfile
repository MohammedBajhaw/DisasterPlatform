FROM ros:foxy-ros-base-focal

# Install lightweight dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-foxy-cartographer \
    ros-foxy-cartographer-ros \
    python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

RUN pip3 install pyserial

# Copy source
COPY src/ /ros2_ws/src/

# Build
WORKDIR /ros2_ws
RUN . /opt/ros/foxy/setup.sh && \
    colcon build --symlink-install --packages-select rplidar_ros hls_lfcd_lds_driver disaster_cartographer sensor_markers

# Setup entrypoint
RUN echo '#!/bin/bash' > /entrypoint.sh && \
    echo 'source /opt/ros/foxy/setup.bash' >> /entrypoint.sh && \
    echo 'source /ros2_ws/install/setup.bash' >> /entrypoint.sh && \
    echo 'exec "$@"' >> /entrypoint.sh && \
    chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
