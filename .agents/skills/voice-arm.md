---
name: voice-arm
description: 语音控制机械臂项目的开发手册。修改本项目代码、排查仿真与训练问题时使用。
---

# voice-arm 项目 skill

## 何时用

- 修改 `ros2_ws/` 下的任何代码
- 排查仿真、训练、语音链路问题
- 新增脚本或测试

## 先读什么

1. `AGENTS.md` —— 边界与冻结契约
2. `docs/architecture.md` —— 两层结构与职责
3. `docs/experiments.md` —— 五阶段验证与当前状态

## 关键约束

- VLM 只做翻译 + 存在性确认，不输出坐标
- 方位（position_hint）与 reply 不进 VLA 输入
- 硬件用度、接口用弧度，转换只在 `RealRobot`
- ROS2 节点薄，逻辑放 `voice_arm_core`

## 常用命令

```bash
make test
python scripts/doctor.py
python scripts/record_sim.py --episodes 2 --duration 2
python scripts/replay_sim.py --steps 50
python scripts/check_language_conditioning.py --instructions "pick up the green cube" "pick up the blue cube"
bash scripts/setup_env.sh --check
```

## 排错顺序

| 现象 | 先查 |
|:---|:---|
| 动作全零 | checkpoint 是否加载（看日志 `policy loaded from`） |
| 状态卡 THINKING | VLM 返回是否合法 JSON、API Key 是否设置 |
| 采集字段缺失 | `python scripts/check_dataset.py --path ...` |
| MuJoCo 加载失败 | 模型路径、`pip install mujoco` |
| 语音无反应 | 先单独测 `TTS().speak("测试")` |

## 不要做

- 不改 `robot/interface.py`、`msg/*.msg`、相机名与关节顺序
- 不在节点里写业务逻辑
- 不提交数据、权重、API Key
