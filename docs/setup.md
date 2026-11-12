# 环境搭建

## 系统要求

- Ubuntu 22.04（推荐）或 Windows + WSL2
- Python 3.10+
- NVIDIA 驱动 + CUDA 12.x

## 安装

```bash
git clone git@github.com:HXM-creator/vlm-vla-voice-arm.git
cd vlm-vla-voice-arm
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

训练依赖：

```bash
pip install -e ".[train]"
```

语音依赖：

```bash
pip install -e ".[audio]"
```

## 环境变量

```bash
export DEEPSEEK_API_KEY="sk-..."
```

不要写进代码或配置文件。

## 串口权限

```bash
sudo usermod -aG dialout $USER
```

重新登录后生效。

## 验证

```bash
make test
make run-sim
```

`run-sim` 使用仿真机器人，不需要硬件。
