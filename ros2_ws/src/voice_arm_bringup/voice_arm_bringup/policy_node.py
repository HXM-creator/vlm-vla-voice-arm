"""策略节点：订阅 TaskCommand -> 发布 ActionChunk。"""
from __future__ import annotations

import rclpy
from rclpy.node import Node

from voice_arm_interfaces.msg import ActionChunk, TaskCommand


class PolicyNode(Node):
    def __init__(self):
        super().__init__("policy_node")
        self.declare_parameter("checkpoint", "")
        self.declare_parameter("action_chunk", 16)
        self.declare_parameter("dof", 6)
        self.pub = self.create_publisher(ActionChunk, "/robot/action_chunk", 10)
        self.create_subscription(TaskCommand, "/task/command", self.on_command, 10)
        self.get_logger().info("policy_node ready")

    def on_command(self, msg: TaskCommand) -> None:
        # TODO: 调用 voice_arm_core.policy.runner.PolicyRunner
        chunk_size = self.get_parameter("action_chunk").value
        dof = self.get_parameter("dof").value
        out = ActionChunk()
        out.chunk_size = chunk_size
        out.dof = dof
        out.actions = [0.0] * (chunk_size * dof)
        self.pub.publish(out)
        self.get_logger().info(f"published action chunk {chunk_size}x{dof}")


def main() -> None:
    rclpy.init()
    node = PolicyNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
