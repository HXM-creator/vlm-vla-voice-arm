# 2026-11-15 环境与训练踩坑记录

记录本次 Ubuntu 环境自检、公开数据集下载、MuJoCo 查看器与 ACT 冒烟训练过程中遇到的问题。API Key 只确认环境变量存在，本文不保存密钥或其内容。

## 当前状态

- Ubuntu 22.04.5、Python 3.10.12、ROS 2 Humble 可用。
- `python3 scripts/doctor.py` 全项通过；MuJoCo 可渲染 front/wrist 两路图像；API Key 被 doctor 检测为已设置。
- 核心单测：37 passed。
- LeRobot 三色 SO-101 数据集已下载到约 1.1 GB 缓存，6 个 mp4 已落盘；缓存中仍看到 30 MiB、20 MiB 的 `.incomplete` 临时文件。训练前建议实际加载数据集验证完整性。
- ACT 500 步 checkpoint 已生成：`outputs/train/act_smoke_retry2/checkpoints/000500/pretrained_model/`。训练进程当前未运行。
- `pip check` 曾报告依赖冲突；版本调整后 Transformers / Hugging Face Hub 冲突消失，仍有 `PyNaCl 1.5.0 is not supported on this platform` 提示。

## 遇到的问题与解法

| 现象 | 原因 | 处理与结论 |
|:---|:---|:---|
| `make test` 报 `python: command not found` | 系统提供 `python3`，Makefile 调用 `python` | 用 `PYTHONPATH=ros2_ws/src/voice_arm_core python3 -m pytest -q`，37 项通过。Makefile 仍可改为兼容 `python3`。 |
| `pytest` 找不到 `voice_arm` | 核心包未安装或源码目录不在模块搜索路径 | 临时设置 `PYTHONPATH=ros2_ws/src/voice_arm_core`；长期可安装核心包 editable。 |
| `pip` 提示 colcon 依赖冲突 | `colcon-core` 缺 pytest 插件，且要求 `setuptools<80` | 曾尝试安装插件和 setuptools 限定版本；中途有一次手动取消。后续 `pip check` 未再列出这些冲突，但保留 PyNaCl 平台提示。 |
| `huggingface-hub` 与 `transformers` 冲突 | LeRobot 0.4.4 约束 Hub `<0.36`，而 Transformers 5.x 需要 Hub `>=1.31` | 将 Hub 固定在 `>=0.34.2,<0.36.0`，Transformers 使用 `>=4.57.1,<5.0.0`；当时实测版本为 Hub 0.35.3、Transformers 4.57.6。 |
| `ImportError: cannot import name AutoProcessor` | 系统 Pillow 9.0.1 缺少 `PIL.Image.Resampling`，Transformers 延迟导入失败 | 用清华 PyPI 镜像安装 `Pillow>=9.1.0`；实际安装 Pillow 12.3.0 后，`from transformers import AutoProcessor` 成功。 |
| 训练报 `policy.repo_id argument missing` | LeRobot 默认尝试推送 Hub，但未提供模型仓库 ID | 本地训练参数加 `--policy.push_to_hub=false`。 |
| HF 下载很久不动、进度条不刷新 | 约 1.05 GB 数据集主要由双相机视频组成；HF endpoint、Xet/CDN 与 PyPI 是不同下载线路。进度显示不总能反映临时文件增长 | 用缓存目录、mp4 和 `.incomplete` 大小判断进度；不要仅凭 GPU 占用判断下载。已完成文件会保留在 HF 缓存中。切换 `HF_HUB_DISABLE_XET` 不能保证更快。 |
| 训练命令退出码 143 | 进程收到 SIGTERM/被中止，训练并未因此完成 | 缓存可复用；重跑时换新的 `--output_dir`，并确认进程开始后没有再次中断。 |
| `find ... -maxdepth 3 -name pretrained_model` 找不到 checkpoint | `pretrained_model` 位于更深层 `checkpoints/000500/pretrained_model`；较早查询时目录也可能尚未生成 | 不限制浅层深度，使用 `find outputs/train/act_smoke_retry2 -path '*/pretrained_model' -type d`。 |
| MuJoCo viewer 一闪而过或看不到 | `SimRobot` 是离屏渲染；独立 viewer 的进程必须保持运行 | 使用 `python3 -m mujoco.viewer --mjcf=ros2_ws/src/voice_arm_core/voice_arm/sim/assets/scene.xml`，并通过 Alt+Tab 切换到标题为 `MuJoCo : scene` 的窗口。 |

## 数据集与仿真边界

- 数据集：`geonmin-kim/SO101-lv4-3color-cube-mat-to-mat-no-human-reset-v1`，约 246 episodes、79,145 帧、约 1.05 GB。
- 数据缓存在 `~/.cache/huggingface/lerobot/geonmin-kim/SO101-lv4-3color-cube-mat-to-mat-no-human-reset-v1/`。
- 本地 MuJoCo `scene.xml` 有 SO-101、front/wrist 相机，但没有抓取方块；viewer 仅展示仿真场景，不会自动连接训练策略。
- 公开数据集的相机/图像域与本地场景不同。完成训练只能证明训练链路可运行，不等于已验证当前场景中的抓取效果。

## 常用检查命令

```bash
# 核心单测
PYTHONPATH=ros2_ws/src/voice_arm_core python3 -m pytest -q

# 环境自检
source ~/.bashrc
python3 scripts/doctor.py

# 查看缓存视频与临时文件
root="$HOME/.cache/huggingface/lerobot/geonmin-kim/SO101-lv4-3color-cube-mat-to-mat-no-human-reset-v1"
find "$root/videos" -type f -name '*.mp4' -printf '%s %p\n'
find "$root/.cache/huggingface/download/videos" -type f -name '*.incomplete' -printf '%s %p\n'

# 查找 checkpoint
find outputs/train/act_smoke_retry2 -path '*/pretrained_model' -type d
```
