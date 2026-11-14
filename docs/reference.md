# 社区参考项目与可借鉴经验

调研时间：2026-11-15。搜索关键词：`so101+mujoco`、`so101+smolvla`、
`so-arm101+imitation+learning`、`so100+vla`、`lerobot+sim+mujoco`。

**结论先说**：没有可以整包复制粘贴的项目。但有 1 个中文踩坑库、1 套真机流程文档、
3 个必须改的参数、1 个数据量参考。

---

## 1. 三个高价值项目

| 项目 | ★ | 用途 | 链接 |
|:---|--:|:---|:---|
| **JereoZero/so101-real** | 43 | **中文**，SO-101 真机全流程 7 篇教程 + 27 条排错 | `github.com/JereoZero/so101-real` |
| **JereoZero/so101-sim** | 14 | 同作者用 **Isaac Lab** 跑通 SO-101 | `github.com/JereoZero/so101-sim` |
| **fouad1233/SO101_Speech_controlled...** | 5 | 语音 → 指令 → VLA 完整 pipeline | `github.com/fouad1233/SO101_Speech_controlled_robotic_arm_with_smolvla` |

其余可参考（未深入）：

| 项目 | ★ | 特点 |
|:---|--:|:---|
| isaka1022/so101-sim2real | 2 | `lerobot_env_*` 插件形式，**自述 IK 不支持垂直抓取** |
| tuul-ai/so101_sim | 35 | 9 个任务（方块拼字、递物、开抽屉），任务组织清晰 |
| huggingface/gym-hil | 官方 | 人在环（HIL），10 分钟训练就能抓 |
| johnsutor/so101-nexus | 53 | 全栈：遥操作 → 模仿学习 → RL |
| RobotControlStack/robot-control-stack | 172 | ROS-free 的 sim-to-real 框架 |

---

## 2. 可直接借鉴的经验（已核实）

### 2.1 `--dataset.video_backend=pyav`（独立验证了我们的 B2）

JereoZero 的排错文档第 13 节原文：

> 训练启动后卡在 `Training: 0%`，日志里有大量
> `OSError: libavutil.so.XX: cannot open shared object file`

原因与我们完全一致：torchcodec 需要 FFmpeg 5–8，Ubuntu 22.04 只有 4.4。
**结论：所有训练命令必须加 `--dataset.video_backend=pyav`。**

### 2.2 `n_action_steps` 必须调小

| 参数 | 我们（默认） | 他们（有效） |
|:---|:--:|:--:|
| `n_action_steps` | **100** | **10** |
| `batch_size` | 4 | 64 |
| `lr` | 1e-5 | 1e-4 |

`n_action_steps=100` = 每 100 步（3.3 秒）才重新推理一次，中间开环执行。
**桌面抓取必然跑偏**，这也解释了回放曲线在 step≈120 的剧烈跳变。

### 2.3 数据量参考

```
199 条 / 52,010 frames / SmolVLA 500M / RTX 5070 12GB → 21/25 = 84% 成功率
```

我们的规划 150–250 条，量级对得上。

### 2.4 训练参数前缀在 0.6.0 变了

| 项 | lerobot 0.4.4（我们） | lerobot 0.6.0（他们） |
|:---|:---|:---|
| batch | `--batch_size` | `--training.batch_size` |
| 学习率 | `--policy.optimizer_lr` | `--training.lr` |
| 输出目录 | `--output_dir` | 移除，用 `--policy.path` |
| 多数据集 | `repo_id='["a","b"]'` | 禁用，改用 `lerobot-edit-dataset --operation.type=merge` |
| 回放 | `lerobot-record --replay` | `lerobot-replay` |
| 成功率评估 | `lerobot-eval` | `lerobot-rollout` |
| 视频后端 | `torchcodec` | `torchcodec`（同样有问题） |

**云端训练必须锁 `lerobot==0.4.4`**，否则参数前缀全部要改。

---

## 3. 他们踩过的坑（27 条摘要）

来源：`JereoZero/so101-real/lerobot-0.6/docs/07-troubleshooting.md`

| # | 问题 | 我们是否会遇到 |
|:--|:---|:---|
| 1 | 串口找不到 | ✅ 真机第一步 |
| 2 | 校准失败 / 范围不对 | ✅ |
| 3 | 夹爪无力 | ✅ |
| 4 | 遥操作时从臂不跟随 | ✅ |
| 5 | 录制时复位阶段无法控制主臂 | ✅ |
| 6 | 训练时 CUDA 报错 | ⚠️ |
| 7 | 训练报 `FileNotFoundError` | ✅ 我们踩过（LeRobotDataset 导入路径） |
| 8 | **推理时动作不稳定** | ✅ **正是我们的 B15** |
| 9 | 摄像头打不开 / 画面异常 | ✅ |
| 10 | **电机通信偶发失败但流程继续** | ⚠️ **静默失败，与我们的坑同类** |
| 11 | 校准报 `TypeError` / `ValueError` | ⚠️ |
| 12 | v0.5 参数在 v0.6 报错 | ✅ 已记录 |
| 13 | **训练卡 0% / torchcodec 失败** | ✅ **我们的 B2** |

**第 10 条最值得警惕**：电机偶发失败但流程继续，数据里混入坏帧却不报错——
和“归一化缺失不报错”是同一类问题。

---

## 4. 架构对比

| 项 | fouad1233（语音项目） | 我们 |
|:---|:---|:---|
| 语音 | Whisper-large-v3 | funasr（未接） |
| 指令映射 | **余弦相似度匹配 100+ 任务描述** | VLM 生成结构化 JSON |
| 策略 | SmolVLA 500M | ACT 52M |
| 环境 | LIBERO-90 + robosuite | 自建 MuJoCo + SO-101 |
| 部署 | Modal A100 单容器 | 本地 / 云端训练 |

**余弦匹配 vs VLM 的取舍**：

| | 余弦匹配 | VLM |
|:---|:---|:---|
| 延迟 | 毫秒级 | 2–5 秒 |
| 成本 | 零 | 按 token 付费 |
| 灵活性 | 只能从固定任务库选 | 能理解新指令 |
| 稳定性 | 高（向量距离确定） | 依赖模型与 JSON 解析 |

**建议**：任务库固定时（绿/蓝/红方块）余弦匹配是更实际的降级路径；
VLM 失败时可自动 fallback 到它。

---

## 5. 不建议照搬

| 项 | 原因 |
|:---|:---|
| isaka1022 的 env 包 | 要求 `lerobot>=0.6.0`，升级成本高；且**自述 IK 不支持垂直抓取**，解决不了我们的问题 |
| Isaac Sim / Isaac Lab | 装 10–15 GB，4060 的 8 GB 显存紧张；从零到能采数据要 2–3 周 |
| gum-pickup / future-breakfast 等玩具项目 | 无文档、无排错记录，参考价值低于上面三个 |
| 整体迁移到 gym-aloha / gymnasium 框架 | 现有 3192 行已跑通，迁移收益只是“更标准” |
