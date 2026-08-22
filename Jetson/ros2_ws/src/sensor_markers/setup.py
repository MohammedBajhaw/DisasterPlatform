from setuptools import find_packages, setup

package_name = 'sensor_markers'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='mohammed',
    maintainer_email='mohammed@todo.todo',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'flame_marker_node = sensor_markers.flame_marker_node:main',
            'simulated_markers_node = sensor_markers.simulated_markers_node:main',
            'lora_tx_node = sensor_markers.lora_tx_node:main',
            'lora_rx_node = sensor_markers.lora_rx_node:main',
            'bno055_node = sensor_markers.bno055_node:main',
            'mpu6050_node = sensor_markers.mpu6050_node:main',
            'wired_sensors_node = sensor_markers.wired_sensors_node:main',
            'simulated_hazards_node = sensor_markers.simulated_hazards_node:main',
            'cognitive_intervention_node = sensor_markers.cognitive_intervention_node:main'
        ],
    },
)
