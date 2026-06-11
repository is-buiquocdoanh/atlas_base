from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('host',       default_value='localhost:8080'),
        DeclareLaunchArgument('fullscreen', default_value='false'),
        Node(
            package='atlas_app_robot',
            executable='atlas_app_robot',
            name='atlas_app_robot',
            output='screen',
            arguments=[
                '--host',       LaunchConfiguration('host'),
                '--fullscreen', LaunchConfiguration('fullscreen'),
            ],
        ),
    ])
