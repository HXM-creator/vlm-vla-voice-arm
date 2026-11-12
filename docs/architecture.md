# 架构说明

## 两层结构

```
使用者语音 → 唤醒 + ASR → 文本
                            ↓
                     VLM（大脑）
              图像 + 文本 → 结构化指令
                            ↓ 唯一接口
                     VLA（小脑）
              图像 + 语言条件 → 动作块
                            ↓
                     机械臂执行 → 语音反馈
```

![架构](../assets/figures/architecture.png)

## 关键约束

1. **VLM 不接触关节空间**：只输出“抓哪个、放哪里”。
2. **VLA 不解析自然语言**：语言条件在训练时注入，推理时只接收编码后的条件向量。
3. **两层可独立替换**：换 VLM 不影响已训练的策略，换策略不需要重写提示词。

## 数据流

![数据流](../assets/figures/flow.png)

## 真机与仿真

`robot/sim.py` 与 `robot/real.py` 实现同一个 `RobotInterface`。
上层代码通过 `configs/*.yaml` 里的 `robot.backend` 切换，不做任何代码分支。
