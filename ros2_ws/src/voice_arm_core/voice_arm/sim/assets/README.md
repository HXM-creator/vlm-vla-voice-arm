# SO-101 仿真模型

本目录的模型文件用于 MuJoCo 仿真，不需要额外下载。

## 文件说明

| 文件 | 用途 |
|:---|:---|
| `scene.xml` | 场景入口，包含机械臂与地面 |
| `so101_new_calib.xml` | MuJoCo 格式的 SO-101，新标定参数（推荐） |
| `so101_old_calib.xml` | 旧标定参数，仅作对照 |
| `so101_new_calib.urdf` / `so101_old_calib.urdf` | URDF 格式，PyBullet 用 |
| `joints_properties.xml` | 关节阻尼、摩擦等参数 |
| `assets/` | 各连杆的 STL 网格 |

## 使用

在 `params.yaml` 里指定场景文件：

```yaml
robot_node:
  ros__parameters:
    sim_xml: ros2_ws/src/voice_arm_core/voice_arm/sim/assets/scene.xml
```

或用命令行：

```bash
python scripts/record_sim.py --sim-xml ros2_ws/src/voice_arm_core/voice_arm/sim/assets/scene.xml
```

## 来源

- 本目录取自 [s0um0r0y/LeRobot-Object-Manipulation-VLM](https://github.com/s0um0r0y/LeRobot-Object-Manipulation-VLM)
  的 `pybullet_sim/lerobot_URDF/`
- 原始 SO-101 结构来自 SO-ARM100 开源项目
- 使用与再分发请遵守上游项目的许可条款

## 相机名

模型里的相机名与接口名可能不同，映射写在 `voice_arm/robot/sim.py`：

```python
DEFAULT_CAMERA_MAP = {"front": "front_cam", "wrist": "wrist_cam"}
```

如果模型里没有相机，`SimRobot` 会回退到合成图像，不会报错。
