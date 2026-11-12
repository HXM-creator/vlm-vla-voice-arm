"""VLM 节点：订阅指令与图像 -> 发布 TaskCommand。"""
from __future__ import annotations

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String

from voice_arm_interfaces.msg import TaskCommand


class VlmNode(Node):
    def __init__(self):
        super().__init__("vlm_node")
        self.declare_parameter("model", "deepseek-flash")
        self.pub = self.create_publisher(TaskCommand, "/task/command", 10)
        self.create_subscription(String, "/voice/instruction", self.on_instruction, 10)
        self.create_subscription(Image, "/camera/front/image_raw", self.on_image, 10)
        self.pending_text: str | None = None
        self.last_image: Image | None = None
        self.get_logger().info("vlm_node ready")

    def on_instruction(self, msg: String) -> None:
        self.pending_text = msg.data
        self.try_process()

    def on_image(self, msg: Image) -> None:
        self.last_image = msg

    def try_process(self) -> None:
        if not self.pending_text or self.last_image is None:
            return
        # TODO: 调用 voice_arm_core.vlm.client.VLMClient，此处先发占位指令
        cmd = TaskCommand()
        cmd.action = "pick_place"
        cmd.target_color = "green"
        cmd.destination_region = "right"
        cmd.reply = "好的，我去拿绿色的方块"
        cmd.confidence = 0.9
        self.pub.publish(cmd)
        self.get_logger().info(f"published task: {self.pending_text}")
        self.pending_text = None


def main() -> None:
    rclpy.init()
    node = VlmNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
