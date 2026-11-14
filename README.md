<div align="center">

# vlm-vla-voice-arm

**说一句中文，机械臂自己去抓**

VLM 负责「听懂并选目标」，VLA 负责「看图并出动作」。<br>
Ubuntu 22.04 · ROS 2 Humble · MuJoCo · LeRobot

![Python](https://img.shields.io/badge/python-3.10+-blue)
![ROS2](https://img.shields.io/badge/ROS2-Humble-22314E)
![Ubuntu](https://img.shields.io/badge/Ubuntu-22.04-E95420)
![Tests](https://img.shields.io/badge/tests-37%20passed-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

[快速开始](#快速开始) · [系统架构](#系统架构) · [仓库结构](#仓库结构) · [进度](#当前进度) · [文档](#文档地图) · [交接](#换机器接续)

</div>

---

## 这是什么

一套桌面机械臂的语音控制系统。使用者说「把绿色的方块放到右边」，
系统完成语音识别、意图理解、目标选择、动作生成与语音回复，全程不需要专用命令词。

与常见方案的区别在于**边界清晰**：VLM 只判断「抓哪个」，位置由 VLA 从图像中学，
不经 VLM 中转坐标。这样语言与动作两层可以独立迭代、独立评估。

---

## 系统架构

![系统架构](assets/figures/architecture.png)

| 层次 | 角色 | 输入 | 输出 |
|:---|:---|:---|:---|
| **VLM** | 大脑 | 中文指令 + 桌面图像 | 固定模板的英文指令 + 目标是否存在 |
| **VLA** | 小脑 | 图像 + 英文指令 | 关节动作块（16 步 × 6 关节） |

**三条不变量：**

- VLM 不输出坐标，只做语义决策
- 方位描述（`position_hint`）与语音回复不进入 VLA 输入
- 真机与仿真共用同一套上层代码，只换 `robot/real.py`

![ROS2 节点拓扑](assets/figures/ros2_graph.png)

---

## 快速开始

```bash
git clone git@github.com:HXM-creator/vlm-vla-voice-arm.git && cd vlm-vla-voice-arm

bash scripts/setup_env.sh --check    # 先看缺什么
bash scripts/setup_env.sh            # 装核心依赖 + 仿真
make test                            # 37 个测试
```

需要训练与语音：

```bash
bash scripts/setup_env.sh --train --audio
```

环境排查：

```bash
python scripts/doctor.py     # 逐项列出缺什么、怎么装
```

> 仓库自带 SO-101 MuJoCo/URDF 模型（16 MB），clone 下来即可用，无需额外下载。

---

## 仓库结构

```
ros2_ws/src/
├── voice_arm_interfaces/      TaskCommand · ActionChunk · RobotStatus
├── voice_arm_core/            纯 Python 核心库（可单测，不依赖 ROS2）
│   └── voice_arm/
│       ├── robot/             interface / sim（MuJoCo）/ real（待实现）
│       ├── vlm/               schema / prompts / client
│       ├── policy/            runner / dataset / train
│       ├── app/               state_machine / orchestrator
│       ├── audio/             wakeword / asr / tts
│       └── sim/assets/        SO-101 模型（16 MB）
└── voice_arm_bringup/         5 个 rclpy 节点 + sim/real 两套 launch

scripts/     setup_env · doctor · record_sim · replay_sim · check_dataset · check_language_conditioning
docs/        decisions · architecture · interface · schema · experiments · setup · handoff · journal/
```

![包结构](assets/figures/packages.png)

---

## 当前进度

| 模块 | 状态 | 说明 |
|:---|:---:|:---|
| ROS2 骨架与话题 | ✅ | 三个包、五个节点、两套 launch |
| 核心库 | ✅ | 37 个测试通过 |
| 仿真后端 | ✅ | 支持 MuJoCo，缺模型时回退合成图像 |
| 数据采集 | ✅ | `record_sim.py`，有 lerobot 写 v3，否则回退 npz |
| 回放与验证 | ✅ | `replay_sim.py`、`check_language_conditioning.py` |
| VLM 接入 | ✅ | 15 s 超时 + 重试，可单命令试用 |
| 语音链路 | ✅ | 唤醒 / ASR / TTS，延迟导入依赖 |
| 端到端演示 | ⏳ | 需 Ubuntu + checkpoint + API Key 实跑 |
| 真机驱动 | ⏳ | 队友实现 `real.py` 的 7 个方法 |

**代码与单测就绪，端到端尚未实跑。** 每个阶段怎么验证见 [docs/experiments.md](docs/experiments.md)，
其中明确区分了「仿真能验证」与「只能真机验证」的项目。

---

## 文档地图

| 文档 | 什么时候看 |
|:---|:---|
| [决策记录](docs/decisions.md) | 想知道为什么这么选、有哪些方案被否掉 |
| [架构说明](docs/architecture.md) | 改代码前先确认职责边界与数据流 |
| [接口契约](docs/interface.md) | 硬件侧实现 `real.py` 时逐条对照 |
| [指令 Schema](docs/schema.md) | 改 VLM 输出字段时看约束与降级规则 |
| [验证流程](docs/experiments.md) | 每个阶段的命令、通过标准、失败排查 |
| [环境搭建](docs/setup.md) | 新机器从零装 ROS2 与依赖 |
| [硬件清单](docs/bom.md) | 选型、价格、采购确认点 |
| [公开数据集](docs/datasets.md) | 无真机时用哪些数据、能验证什么 |
| [团队文档](docs/team/) | 给硬件侧的分工与确认清单 |
| [换机器接续](docs/handoff.md) | 从 Windows 换到 Ubuntu 时按此走 |
| [会话记录](docs/journal/) | 上次做到哪、遗留什么问题 |

给 AI 助手的说明见 [AGENTS.md](AGENTS.md) 与 [.agents/skills/voice-arm.md](.agents/skills/voice-arm.md)。

---

## 开发约定

下面三项**一旦确定不能单方面修改**，改动会导致已采集数据失效：

1. `voice_arm/robot/interface.py` 的 7 个方法签名与单位（弧度）
2. `voice_arm_interfaces/msg/*.msg` 的字段
3. 数据字段：相机名 `front` / `wrist`、关节顺序

分支与提交规范见 [CONTRIBUTING.md](CONTRIBUTING.md)。

```bash
git checkout -b feat/your-feature      # main 受保护，不直接推
make test                              # 提交前必须全绿
```

---

## 参考

- [LeRobot](https://github.com/huggingface/lerobot) — 数据格式、训练与推理框架
- [SmolVLA](https://arxiv.org/abs/2506.01844) — 轻量视觉语言动作模型（450M）
- [ACT](https://arxiv.org/abs/2304.13705) — 动作分块模仿学习
- [OpenVLA](https://github.com/openvla/openvla) — 开源 VLA 参考实现

---

## 许可

[MIT](LICENSE)。仿真模型来源见 [assets/README.md](ros2_ws/src/voice_arm_core/voice_arm/sim/assets/README.md)。
