# 硬件接口契约

## 抽象接口

`ros2_ws/src/voice_arm_core/voice_arm/robot/interface.py` 定义 `RobotInterface`，共 7 个方法：

| 方法 | 输入 | 输出 | 频率 |
|---|---|---|---|
| `connect(port)` | 串口路径 | bool | 启动一次 |
| `disconnect()` | - | - | 结束一次 |
| `get_joint_positions()` | - | `ndarray(6,)` 弧度 | ≥30 Hz |
| `set_joint_positions(q)` | `ndarray(6,)` 弧度 | - | ≥30 Hz |
| `get_gripper_state()` | - | float 0~1 | ≥30 Hz |
| `set_gripper(v)` | float 0~1 | - | 事件触发 |
| `get_frames()` | - | `{front, wrist}` BGR | ≥30 fps |

## ROS2 侧对应关系

| 抽象接口 | ROS2 话题 | 说明 |
|---|---|---|
| `set_joint_positions` | `/robot/action_chunk` | 策略输出，robot_node 订阅 |
| `get_joint_positions` | `/robot/joint_states` | `sensor_msgs/JointState` |
| `get_gripper_state` / `set_gripper` | `/robot/status` + 参数 | 或自定义服务 |
| `get_frames` | `/camera/front/image_raw` | `sensor_msgs/Image` |

## 约定

- 角度单位统一为**弧度**；硬件若以度为单位，在驱动层转换。
- 单次调用超时 **100 ms**。
- 上电后先安全复位。
- 图像为 **BGR 三通道 ndarray**，分辨率与帧率固定。

## 验收标准

1. 移动到指定角度，误差 < 2°。
2. 30 Hz 连续读回 10 分钟无丢包。
3. 夹爪开合值与实际位置一致。
4. 双相机同时 30 fps 出图。
5. 连续运行 30 分钟不丢步、不掉线。
