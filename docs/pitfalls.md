# 踩坑与错误汇总

汇总 2026-11-14 至 11-15 两天在 Ubuntu 22.04 + SO-101 仿真链路上踩到的全部问题。
按类别组织，每条记录**现象、根因、修复、教训**。

> 这份文档的价值不在"记录了什么"，而在于**同类问题在真机上会重复出现**，
> 且其中一半是**不报错但结果错**的隐蔽问题。

---

## 一、环境与依赖

### 1.1 `make test` 报 `python: 未找到`

- **现象**：README 的第一步就失败
- **根因**：Makefile 硬编码 `python`，Ubuntu 22.04 只有 `python3`
- **修复**：`PYTHON ?= python3`（待改）；临时用 `python3 -m pytest -q`
- **教训**：项目在 Windows 上开发，Linux 入口从未验证

### 1.2 `torchcodec` 加载失败

- **现象**：`Could not load libtorchcodec`，`libavutil.so.57~60` 全部找不到
- **根因**：torchcodec 需 FFmpeg 5–8，Ubuntu 22.04 只有 4.4（`.56`）
- **修复**：`--dataset.video_backend=pyav`（PyAV 自带 FFmpeg）
- **教训**：社区项目 JereoZero 也踩了同一坑，属于 Ubuntu 22.04 通病

### 1.3 `AutoProcessor` 导入失败

- **现象**：`ImportError: cannot import name AutoProcessor`
- **根因**：系统 Pillow 9.0.1 缺 `PIL.Image.Resampling`，Transformers 延迟导入失败
- **修复**：升级 Pillow ≥ 9.1（实测 12.3.0）

### 1.4 依赖版本冲突

- **现象**：`huggingface-hub` 与 `transformers` 互斥
- **根因**：LeRobot 0.4.4 约束 Hub `<0.36`，Transformers 5.x 需 Hub `>=1.31`
- **修复**：锁 Hub `0.35.3` + Transformers `4.57.x`
- **教训**：云端训练必须锁版本（`lerobot==0.4.4`），否则参数前缀都会变

### 1.5 视频播放器打不开

- **现象**：`xdg-open` 报 `GLIBCXX_3.4.29 not found`
- **根因**：snap 的 core20 库与系统 libproxy 冲突，与视频无关
- **修复**：`google-chrome file.mp4` 或 `vlc file.mp4`

---

## 二、数据管道

### 2.1 `LeRobotDataset` 导入路径变更（静默回退）

- **现象**：采集日志出现 `[WARN] 写入 LeRobotDataset 失败`，然后静默写出 npz
- **根因**：lerobot 0.4.4 不再从 `lerobot.datasets` 顶层导出，需从 `lerobot.datasets.lerobot_dataset` 导入
- **修复**：改正导入路径；显式 `--format lerobot` 时不再静默回退
- **教训**：**静默降级是最危险的**——以为拿到了 lerobot 格式，训练时才发现读不了

### 2.2 采集视频颜色反转（BGR/RGB）

- **现象**：机械臂变青色、地面变棕色
- **根因**：`SimRobot` 按接口约定返回 BGR，lerobot 数据集约定 RGB，直接透传导致通道互换
- **修复**：写入数据集前 `[:, :, ::-1]` 转 RGB
- **教训**：**训练不会报错**，只会让模型学到错误的颜色分布

### 2.3 采集被 OOM 杀死

- **现象**：夜间任务在第 47 条被 `Killed`
- **根因**：所有 episode 攒在内存里，每条 89 帧 × 2 相机 × 0.9 MB ≈ 160 MB，70 条约 7.5 GB
- **修复**：改为流式写入（采一条写一条 + `del frames`），50 条实测峰值 1.59 GB
- **教训**：150 条永远跑不完；**采集脚本必须流式**

### 2.4 多任务数据集

- **现象**：想用三个目录分别采三个颜色，训练时报 `NotImplementedError`
- **根因**：lerobot 0.4.4 的 `MultiLeRobotDataset` 被禁用
- **修复**：`record_sim.py` 加 `--tasks`，每个任务各采 N 条写进同一数据集

### 2.5 输出目录已存在

- **现象**：`File exists`，然后静默回退 npz
- **修复**：`LeRobotDataset.create` 前检查目录，非空则报错退出

### 2.6 数据集统计显示"6 帧"

- **现象**：3 条数据却汇总成 6 帧
- **根因**：`episodes` 变成 `(task, frames)` 元组后，`len(e)` 算的是元组长度
- **修复**：`sum(len(frames) for _, frames in episodes)`

---

## 三、训练

### 3.1 训练参数前缀（0.6.0 变更）

| 项 | 0.4.4 | 0.6.0 |
|:---|:---|:---|
| batch | `--batch_size` | `--training.batch_size` |
| lr | `--policy.optimizer_lr` | `--training.lr` |
| 输出目录 | `--output_dir` | 移除 |

**教训**：云端锁版本，否则整套命令都要改。

### 3.2 `n_action_steps` 过大

- **现象**：回放动作曲线每 100 步剧烈跳变
- **根因**：默认 100 = 每 3.3 秒才重新推理，中间开环执行
- **修复**：改为 10（社区推荐值）

### 3.3 显存与 batch

- 8 GB 显存跑 ACT 52M，batch 4 稳定（约 5 GB），batch 8 有余量但不建议
- SmolVLA 500M 默认冻结视觉编码器 + 只训 expert，显存友好

### 3.4 训练速度参考

| 环境 | 速度 |
|:---|:---|
| CPU（沙箱） | 1.4 s/step |
| 4060（batch 4） | 约 0.28 s/step（5.5 step/s） |

15000 步在 4060 上约 45 分钟。

---

## 四、推理

### 4.1 跳过 pre/post processor（最严重）

- **现象**：动作数值在 ±0.5 徘徊，机械臂乱动但不报错
- **根因**：lerobot 0.4 的 ACT **不在 policy 内部做归一化**，而是描述在 `policy_preprocessor.json` / `policy_postprocessor.json`
- **修复**：`pre → select_action → post`，再按单位转弧度
- **验证**：归一化空间输出 -0.74~0.54；反归一化后 -86.28~71.82（度）
- **教训**：**不报错、数值错**，是最难查的一类

### 4.2 单位混用（弧度 vs 度）

- **现象**：动作差 57 倍，关节打满限位
- **根因**：`RobotInterface` 用弧度，公开数据集用度（SO-101 官方默认 `use_degrees=True`）
- **修复**：按数据集统计量自动检测单位（跨度 > 10 判为度），再 `deg2rad`
- **注意**：gripper 用 `RANGE_0_100`，范围比其他关节小，检测阈值仍成立

### 4.3 相机键硬编码

- **现象**：`KeyError: 'observation.images.wrist'`
- **根因**：`_to_batch` 写死 `camera1/camera2`，而数据集用 `top/wrist` 或 `front/wrist`
- **修复**：按 checkpoint 的 `input_features` 动态映射

### 4.4 缺 `observation.state`

- **现象**：推理报缺字段
- **根因**：`predict()` 签名没有 state 参数
- **修复**：新增 `state` 入参，调用方传 `robot.get_joint_positions()`

### 4.5 GPU tensor 转 numpy

- **现象**：`can't convert cuda:0 device type tensor to numpy`
- **修复**：`action.detach().cpu().numpy()`

---

## 五、仿真渲染

### 5.1 模型没有相机

- **现象**：`camera "front_cam" does not exist`
- **根因**：`so101_new_calib.xml` 里 `ncam=0`
- **修复**：在 `scene.xml` 加 `front_cam`，在 `gripper` body 加 `wrist_cam`

### 5.2 渲染一片棕色

- **现象**：所有几何体堆在原点
- **根因**：`MjData` 未 `mj_forward`，`xpos` 全 0
- **修复**：`_load_mujoco` 末尾补一次 forward

### 5.3 GLFW 后端不可用

- **现象**：`gladLoadGL error`
- **修复**：`export MUJOCO_GL=egl`

### 5.4 相机背对机械臂

- **现象**：只拍到空桌面
- **根因**：机械臂朝 **+x** 伸展，相机放在了 `x=-0.30`
- **修复**：用自由相机扫参，选中 `az=90, el=-26, dist=0.62` 后反算 `pos/xyaxes`

### 5.5 方块不会被带走

- **现象**：夹爪闭合了，方块留在原地
- **根因**：`SimRobot` 只做 `mj_forward` 不做 `mj_step`，没有接触力
- **修复**：运动学挂载——闭合时刻记录方块相对夹爪偏移，之后每帧搬运
- **注意**：回放/录制脚本也要有同样逻辑，否则永远看不到抓取

### 5.6 采集太慢

- **现象**：210 ms/帧，150 条约 75 分钟
- **根因**：阴影 + 反射占 68% 渲染开销
- **修复**：`fast_render=True` 关闭两者 → 67 ms/帧（3.2 倍）

---

## 六、策略能力

### 6.1 ACT 不读 task（决定性发现）

- **现象**：三色数据训练 15000 步，三种指令的动作距离仅 0.00016
- **根因**：`grep` 实测 ACT `forward` 处理 `task` 的代码行数为 **0**；SmolVLA / π0 为 6
- **修复**：语言条件必须换 SmolVLA / π0；ACT 只能做单任务
- **教训**：选策略前先查它是否真的用了语言输入

### 6.2 公开数据集的 `effective` 是假象

- **现象**：geonmin-kim 数据测得 0.0135 距离，判定 effective
- **根因**：该数据集颜色与位置绑定（每种颜色固定 mat），加上 ACT 的 VAE 采样随机性
- **教训**：语言条件验证必须**固定场景只换指令**，且模型真的读指令

---

## 七、方法论：如何避免静默失败

两天踩的坑里，**一半是"不报错但结果错"**。总结三条排查原则：

### 7.1 警惕 `except Exception` 兜底

```python
# 危险：错误被吞掉，系统"看起来在跑"
except Exception as exc:
    log.warning("失败（%s），保持零动作回退", exc)
    return zeros
```

**改法**：连续失败 N 次抛错；首次失败用 `error` 级别；对外暴露 `healthy` / `load_error`。

### 7.2 关键数值要有断言

| 检查 | 阈值 |
|:---|:---|
| 关节角是否在限位内 | 超出即报错（本次 99 rad → 1.92/1.75） |
| 动作是否在弧度范围 | `abs(a) < π` |
| 单位是否正确 | 跨度 > 10 判为度 |
| 图像颜色是否正常 | 黄色机械臂像素占比 > 0.5% |

### 7.3 端到端冒烟测试

`scripts/smoke_test.py` 30 秒检查四项：

```
环境 → 渲染（含颜色通道）→ 采集（含动作对齐）→ 推理（含单位与限位）
```

**改完任何代码先跑它**，能挡住 90% 的同类问题。

---

## 附：问题分布统计

| 类别 | 数量 | 其中"静默失败" |
|:---|--:|--:|
| 环境依赖 | 5 | 1 |
| 数据管道 | 6 | 4 |
| 训练 | 4 | 1 |
| 推理 | 5 | 3 |
| 仿真渲染 | 6 | 3 |
| 策略能力 | 2 | 1 |
| **合计** | **28** | **13（46%）** |

**近一半问题不会报错**——这是本项目最值得记录的工程经验。
