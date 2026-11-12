"""硬件节点：订阅动作块 -> 驱动机械臂；发布关节状态与图像。

真机实现由硬件负责人补全；当前为仿真回退。
"""
from __future__ import annotations

import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, JointState

from voice_arm_interfaces.msg import ActionChunk, RobotStatus


class RobotNode(Node):
    def __init__(self):
        super().__init__("robot_node")
        self.declare_parameter("backend", "sim")
        self.declare_parameter("dof", 6)
        self.declare_parameter("control_hz", 30)

        self.status_pub = self.create_publisher(RobotStatus, "/robot/status", 10)
        self.joint_pub = self.create_publisher(JointState, "/robot/joint_states", 10)
        self.image_pub = self.create_publisher(Image, "/camera/front/image_raw", 10)
        self.create_subscription(ActionChunk, "/robot/action_chunk", self.on_chunk, 10)

        self.q = np.zeros(self.get_parameter("dof").value, dtype=np.float32)
        self.gripper = 0.0
        hz = self.get_parameter("control_hz").value
        self.create_timer(1.0 / hz, self.publish_status)
        self.get_logger().info("robot_node ready")

    def on_chunk(self, msg: ActionChunk) -> None:
        if msg.chunk_size == 0:
            return
        first = list(msg.actions[: msg.dof])
        self.q = np.asarray(first, dtype=np.float32)
        # TODO: 调用 voice_arm_core.robot.real.RealRobot.set_joint_positions

    def publish_status(self) -> None:
        st = RobotStatus()
        st.joint_positions = [float(x) for x in self.q]
        st.gripper = float(self.gripper)
        st.connected = True
        st.state = "EXECUTING"
        self.status_pub.publish(st)


def main() -> None:
    rclpy.init()
    node = RobotNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
