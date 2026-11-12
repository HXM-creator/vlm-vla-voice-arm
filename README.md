# vlm-vla-voice-arm

基于 **VLM 大脑 + VLA 小脑** 的中文语音控制机械臂系统。使用者用日常口语下达抓放指令，机械臂完成目标选择、抓取与放置，并以语音回复结果。

![系统架构](assets/figures/architecture.png)

## 系统架构

系统分为两层，两层之间以结构化指令为唯一接口：

| 层次 | 角色 | 输入 | 输出 |
|---|---|---|---|
| VLM | 大脑 | 指令文本 + 桌面图像 | 结构化动作指令（抓哪个、放哪里） |
| VLA | 小脑 | 图像 + 语言条件 | 关节动作块（16 步 × 6 关节） |

- VLM 不接触关节空间，VLA 不解析自然语言
- 任一层的模型更换都不影响另一层
- 真机与仿真共用同一套上层代码

## 目录结构

```
src/voice_arm/
├── audio/    语音唤醒、识别、合成
├── vlm/      意图理解与指令校验
├── policy/   VLA 推理与训练
├── robot/    硬件抽象层（真机 / 仿真双实现）
├── app/      状态机与主循环
└── utils/    配置与日志
```

## 快速开始

```bash
# 1. 安装
pip install -e ".[dev]"

# 2. 跑测试
make test

# 3. 用仿真机器人启动（无需硬件）
make run-sim
```

仿真实现返回固定的关节角与合成图像，可以在硬件到货前跑通语音 → VLM → 策略 → 执行的完整链路。

## 硬件状态

| 部分 | 状态 |
|---|---|
| 机械臂平台 | 选型中（接口已固定，见 `docs/interface.md`） |
| 相机 | 选型中 |
| 计算平台 | RTX 4060 Laptop（8 GB） |

`src/voice_arm/robot/real.py` 由硬件负责人按 `docs/interface.md` 实现，接口契约变更需双方确认。

## 训练

```bash
bash scripts/record_data.sh     # 主从遥操作采集
bash scripts/train_act.sh       # ACT 基线（8 GB 可训）
bash scripts/train_smolvla.sh   # SmolVLA + LoRA（需更小批大小）
```

数据格式统一为 LeRobotDataset v3，真机与仿真产出的数据可直接混合训练。

## 文档

- [架构说明](docs/architecture.md)
- [接口契约](docs/interface.md)
- [指令 Schema](docs/schema.md)
- [环境搭建](docs/setup.md)

## 参考

- [LeRobot](https://github.com/huggingface/lerobot) — 数据格式、训练与推理框架
- [SmolVLA](https://arxiv.org/abs/2506.01844) — 轻量视觉语言动作模型
- [ACT](https://arxiv.org/abs/2304.13705) — 动作分块模仿学习

## 许可

MIT
