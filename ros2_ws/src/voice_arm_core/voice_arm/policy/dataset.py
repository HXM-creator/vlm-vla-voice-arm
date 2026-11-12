"""LeRobotDataset v3 封装说明。

数据目录结构由 LeRobot 管理，本模块只提供与本项目约定相关的常量。
"""
from __future__ import annotations

# 字段约定，与 docs/architecture.md 一致
STATE_KEY = "observation.state"          # shape (6,)  弧度
ACTION_KEY = "action"                    # shape (6,)  弧度
CAMERA_KEYS = ("observation.images.camera1", "observation.images.camera2")
TASK_KEY = "task"

# smolvla_base 期望的相机名；训练与推理都要做这个映射
RENAME_MAP = {
    "observation.images.front": "observation.images.camera1",
    "observation.images.wrist": "observation.images.camera2",
}
