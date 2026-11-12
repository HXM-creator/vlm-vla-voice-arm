"""语音节点：唤醒 + ASR -> /voice/instruction；订阅 /voice/reply 播报。"""
from __future__ import annotations

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class AudioNode(Node):
    def __init__(self):
        super().__init__("audio_node")
        self.pub = self.create_publisher(String, "/voice/instruction", 10)
        self.sub = self.create_subscription(String, "/voice/reply", self.on_reply, 10)
        self.get_logger().info("audio_node ready")

    def on_reply(self, msg: String) -> None:
        # TODO: 接入 edge-tts 播放
        self.get_logger().info(f"reply: {msg.data}")

    def publish_instruction(self, text: str) -> None:
        self.pub.publish(String(data=text))


def main() -> None:
    rclpy.init()
    node = AudioNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
