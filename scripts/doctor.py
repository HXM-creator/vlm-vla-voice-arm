#!/usr/bin/env python3
"""环境自检：逐项检查依赖与文件，给出可执行的修复建议。

用法：
    python scripts/doctor.py
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "ros2_ws" / "src" / "voice_arm_core"
SCENE = CORE / "voice_arm" / "sim" / "assets" / "scene.xml"

OK = "OK  "
WARN = "WARN"
FAIL = "FAIL"
INFO = "INFO"


def has(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def row(name: str, status: str, detail: str, fix: str = "") -> None:
    print(f"  [{status}] {name:<22} {detail}")
    if fix and status in (WARN, FAIL):
        print(f"         -> {fix}")


def main() -> int:
    problems = 0
    print("环境自检\n" + "=" * 64)

    row("Python", OK if sys.version_info >= (3, 10) else FAIL,
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "需要 3.10+")

    for mod, name, fix in [
        ("numpy", "numpy", "pip install numpy"),
        ("mujoco", "mujoco", "pip install 'mujoco>=3.0'"),
        ("cv2", "opencv-python", "pip install opencv-python"),
        ("yaml", "pyyaml", "pip install pyyaml"),
        ("openai", "openai", "pip install 'openai>=1.30'"),
        ("torch", "torch", "pip install torch torchvision"),
        ("lerobot", "lerobot", "pip install 'lerobot>=0.4'"),
        ("sounddevice", "sounddevice", "pip install sounddevice"),
        ("funasr", "funasr", "pip install 'funasr>=1.1'"),
        ("edge_tts", "edge-tts", "pip install 'edge-tts>=6.1'"),
        ("openwakeword", "openWakeWord", "pip install 'openwakeword>=0.6'"),
    ]:
        if has(mod):
            row(name, OK, "已安装")
        else:
            # 核心依赖缺失才算问题，其余给警告
            status = FAIL if mod in ("numpy", "yaml") else WARN
            if status == FAIL:
                problems += 1
            row(name, status, "未安装", fix)

    distro = os.environ.get("ROS_DISTRO", "")
    if distro:
        row("ROS2", OK, f"ROS_DISTRO={distro}")
    elif Path("/opt/ros/humble").exists():
        row("ROS2", WARN, "已安装但未 source", "source /opt/ros/humble/setup.bash")
    else:
        row("ROS2", WARN, "未检测到", "见 docs/setup.md 第 1 节")

    if SCENE.exists():
        size_mb = sum(f.stat().st_size for f in SCENE.parent.rglob("*") if f.is_file()) / 1e6
        row("模型文件", OK, f"scene.xml（目录 {size_mb:.1f} MB）")
    else:
        row("模型文件", WARN, "缺少 scene.xml",
            "git clone 完整仓库；或 bash scripts/download_sim_model.sh")
        problems += 1

    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if key:
        row("VLM API Key", OK, f"已设置（{len(key)} 字符）")
    else:
        row("VLM API Key", WARN, "未设置", "export DEEPSEEK_API_KEY='sk-...'")

    try:
        import numpy as np
        sys.path.insert(0, str(CORE))
        from voice_arm.robot.sim import SimRobot

        robot = SimRobot(image_size=(64, 80), xml_path=SCENE if SCENE.exists() else None)
        frames = robot.get_frames()
        row("仿真渲染", OK,
            f"{'MuJoCo' if SCENE.exists() and has('mujoco') else '合成图像'}，"
            f"{len(frames)} 路相机，{frames['front'].shape}")
    except Exception as exc:  # noqa: BLE001
        row("仿真渲染", FAIL, f"{exc}", "检查 numpy 与模型路径")
        problems += 1

    print("=" * 64)
    if problems:
        print(f"发现 {problems} 个阻塞项，按上面的建议处理后重跑本脚本。")
        return 1
    print("环境可用。跑 `make test` 验证代码，或 `python scripts/record_sim.py --episodes 1` 采一条数据。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
