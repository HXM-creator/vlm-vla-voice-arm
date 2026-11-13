# AGENTS.md

给 AI 助手（Claude Code / Reasonix / Cursor 等）的项目说明。开始改动前先读完本文。

## 这个项目是什么

桌面机械臂的中文语音控制：VLM 把口语转成英文任务指令，VLA 根据图像与指令生成关节动作。
运行环境 **Ubuntu 22.04 + ROS2 Humble**，仿真用 MuJoCo，训练用 LeRobot。

## 架构与边界

```
语音 → 文本 → VLM（只翻译 + 确认目标存在）→ 英文指令 → VLA（看图 + 出动作）→ 机械臂
```

**三条不能违反的边界：**

1. **VLM 不输出坐标**，只输出固定模板的英文指令、目标存在性、粗略方位（仅用于对话）。
2. **方位与回复文本不进入 VLA 输入**，证据在 `vlm/schema.py::to_vla_instruction` 与对应测试。
3. **节点只做消息转换**，核心逻辑在 `voice_arm_core`，不写进 ROS2 节点。

## 三个冻结契约（改之前必须双方确认）

| 位置 | 内容 |
|:---|:---|
| `voice_arm/robot/interface.py` | 7 个方法的签名与单位（弧度） |
| `voice_arm_interfaces/msg/*.msg` | 消息字段 |
| 数据字段 | 相机名 `front` / `wrist`、关节顺序 |

改动会影响已采集的数据，必须重采。PR 模板里有勾选项。

## 目录速查

```
ros2_ws/src/voice_arm_core/      核心库（纯 Python，可单测）
  voice_arm/robot/               interface / sim / real
  voice_arm/vlm/                 schema / prompts / client
  voice_arm/policy/              runner / dataset / train
  voice_arm/app/                 state_machine / orchestrator
  voice_arm/audio/               wakeword / asr / tts
  voice_arm/sim/assets/          SO-101 MuJoCo 模型（16 MB，已入库）
  tests/                         37 个测试
ros2_ws/src/voice_arm_bringup/   ROS2 节点 + launch
scripts/                         采集 / 训练 / 回放 / 自检
docs/                            架构 / 接口 / schema / 环境 / 验证
```

## 常用命令

```bash
make test                                    # 37 个测试，不需要 ROS2
bash scripts/setup_env.sh --check            # 环境检查
python scripts/doctor.py                     # 同上，输出更细
python scripts/record_sim.py --episodes 2    # 仿真采数据
python scripts/replay_sim.py --steps 50      # 回放
cd ros2_ws && colcon build && ros2 launch voice_arm_bringup sim.launch.py
```

## 代码约定

- 角度：硬件层用**度**，`RobotInterface` 用**弧度**，转换只在 `RealRobot` 一处。
- 依赖：音频、训练、ROS2 全部**延迟导入**，缺依赖时抛可读错误，不能让 `import` 失败。
- 日志：用 `logging`，不用 `print`（脚本的最终结果除外）。
- 测试：新增功能必须带测试，`make test` 保持全绿。
- 提交：`<type>: <说明>`，type 取 feat / fix / docs / refactor / test / chore。

## 当前状态

代码与单测就绪（37 通过），**端到端未在 Ubuntu 实跑**。
每个阶段的验证方法见 `docs/experiments.md`，其中明确区分了仿真能验证什么、不能验证什么。

## 不要做

- 不要为了"看起来完整"加空壳模块
- 不要改冻结契约而不通知
- 不要把数据、模型权重、API Key 提交进仓库
- 不要在节点里写业务逻辑
