"""总控节点：状态机 + 语音反馈。"""
from __future__ import annotations

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from voice_arm_interfaces.msg import RobotStatus, TaskCommand


class OrchestratorNode(Node):
    def __init__(self):
        super().__init__("orchestrator_node")
        self.reply_pub = self.create_publisher(String, "/voice/reply", 10)
        self.create_subscription(TaskCommand, "/task/command", self.on_command, 10)
        self.create_subscription(RobotStatus, "/robot/status", self.on_status, 10)
        self.state = "IDLE"
        self.get_logger().info("orchestrator_node ready")

    def on_command(self, msg: TaskCommand) -> None:
        self.state = "EXECUTING"
        if msg.reply:
            self.reply_pub.publish(String(data=msg.reply))
        self.get_logger().info(f"state -> {self.state}")

    def on_status(self, msg: RobotStatus) -> None:
        # TODO: 用 voice_arm_core.app.state_machine.StateMachine 管理迁移
        pass


def main() -> None:
    rclpy.init()
    node = OrchestratorNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
