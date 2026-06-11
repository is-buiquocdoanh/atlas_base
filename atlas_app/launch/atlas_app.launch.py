from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='atlas_app',
            executable='atlas_app',
            name='atlas_app',
            output='screen',
        ),
    ])
