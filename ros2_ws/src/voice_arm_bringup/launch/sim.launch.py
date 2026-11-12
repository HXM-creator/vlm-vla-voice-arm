from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(package="voice_arm_bringup", executable="audio_node", name="audio_node"),
        Node(package="voice_arm_bringup", executable="vlm_node", name="vlm_node"),
        Node(package="voice_arm_bringup", executable="policy_node", name="policy_node",
             parameters=[{"action_chunk": 16, "dof": 6}]),
        Node(package="voice_arm_bringup", executable="robot_node", name="robot_node",
             parameters=[{"backend": "sim", "dof": 6, "control_hz": 30}]),
        Node(package="voice_arm_bringup", executable="orchestrator_node", name="orchestrator_node"),
    ])
