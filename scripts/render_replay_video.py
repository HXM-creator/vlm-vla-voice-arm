#!/usr/bin/env python3
"""把策略在仿真里的执行过程录成视频。

左右并排 front / wrist 两路相机，逐帧写入 mp4。
不依赖 ffmpeg 命令，用 OpenCV 自带的 mp4v 编码器。
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ros2_ws/src/voice_arm_core"))

from voice_arm.policy.runner import PolicyRunner  # noqa: E402
from voice_arm.robot.sim import SimRobot  # noqa: E402


def parse_size(text: str) -> tuple[int, int]:
    h, w = (int(x) for x in text.split(","))
    return h, w


def main() -> None:
    ap = argparse.ArgumentParser(description="录制策略在仿真中的执行视频")
    ap.add_argument("--checkpoint", default="", help="训练好的 checkpoint 目录")
    ap.add_argument("--steps", type=int, default=150)
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--image-size", default="480,640", help="高,宽")
    ap.add_argument("--sim-xml", default="")
    ap.add_argument("--instruction", default="pick up the green cube")
    ap.add_argument("--device", default="cuda", help="推理设备：cuda / cpu")
    ap.add_argument("--output", default="outputs/replay/rollout.mp4")
    args = ap.parse_args()

    h, w = parse_size(args.image_size)
    robot = SimRobot(dof=6, image_size=(h, w),
                     xml_path=args.sim_xml or None, cameras=("front", "wrist"))
    robot.connect()
    policy = PolicyRunner(checkpoint=args.checkpoint or None, action_chunk=1, dof=6,
                          device=args.device)

    out_path = ROOT / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), args.fps, (w * 2, h)
    )
    if not writer.isOpened():
        raise SystemExit("无法创建视频文件，检查 OpenCV 的 mp4v 编码支持")

    started = time.monotonic()
    try:
        for i in range(args.steps):
            frames = robot.get_frames()
            act = policy.predict(
                frames, instruction=args.instruction, state=robot.get_joint_positions()
            )
            robot.set_joint_positions(act[0])

            canvas = np.hstack([frames["front"], frames["wrist"]])
            cv2.putText(canvas, f"front | wrist   step {i:03d}", (10, 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(canvas, args.instruction, (10, h - 14),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1, cv2.LINE_AA)
            writer.write(canvas)
    finally:
        writer.release()

    elapsed = time.monotonic() - started
    size_kb = out_path.stat().st_size / 1024
    print(f"已写入 {out_path}")
    print(f"  {args.steps} 帧 @ {args.fps} fps = {args.steps / args.fps:.1f} 秒视频")
    print(f"  分辨率 {w * 2}x{h}，文件 {size_kb:.0f} KB，耗时 {elapsed:.1f}s")


if __name__ == "__main__":
    main()
