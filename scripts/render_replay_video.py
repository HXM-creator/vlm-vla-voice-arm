#!/usr/bin/env python3
"""把策略在仿真里的执行过程录成视频。

左右并排 front / wrist 两路相机，逐帧写入 mp4。
不依赖 ffmpeg 命令，用 OpenCV 自带的 mp4v 编码器。

注意：SimRobot 只做运动学（mj_forward），不做物理步进，夹爪闭合不会产生
接触力。因此这里复刻 record_sim 的「运动学抓取」：夹爪接近目标方块且闭合后，
把方块挂到夹爪上，使视频能反映策略的意图。
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

COLOR_TO_BODY = {"green": "cube_green", "blue": "cube_blue", "red": "cube_red"}


def parse_size(text: str) -> tuple[int, int]:
    h, w = (int(x) for x in text.split(","))
    return h, w


def detect_target(instruction: str) -> str | None:
    lower = instruction.lower()
    for color, body in COLOR_TO_BODY.items():
        if color in lower:
            return body
    return None


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
    ap.add_argument("--grasp-dist", type=float, default=0.06,
                    help="夹爪与方块中心距离小于此值时视为抓住（米）")
    args = ap.parse_args()

    h, w = parse_size(args.image_size)
    robot = SimRobot(dof=6, image_size=(h, w),
                     xml_path=args.sim_xml or None, cameras=("front", "wrist"),
                     fast_render=True)
    robot.connect()
    policy = PolicyRunner(checkpoint=args.checkpoint or None, action_chunk=1, dof=6,
                          device=args.device)

    import mujoco

    from voice_arm.sim.kinematics import site_id

    model, data = robot.model, robot.data
    target_body = detect_target(args.instruction)
    cube_bid = cube_adr = site = None
    if model is not None and target_body:
        cube_bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, target_body)
        if cube_bid >= 0:
            cube_adr = int(model.jnt_qposadr[model.body_jntadr[cube_bid]])
            site = site_id(model)

    out_path = ROOT / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), args.fps, (w * 2, h)
    )
    if not writer.isOpened():
        raise SystemExit("无法创建视频文件，检查 OpenCV 的 mp4v 编码支持")

    started = time.monotonic()
    attached = False
    dists: list[float] = []
    min_dist = float("inf")
    try:
        for i in range(args.steps):
            frames = robot.get_frames()
            act = policy.predict(
                frames, instruction=args.instruction, state=robot.get_joint_positions()
            )
            robot.set_joint_positions(act[0])

            if cube_adr is not None:
                mujoco.mj_forward(model, data)
                gripper = np.asarray(data.site_xpos[site], dtype=np.float64)
                cube = np.asarray(data.xpos[cube_bid], dtype=np.float64)
                d = float(np.linalg.norm(gripper - cube))
                dists.append(d)
                min_dist = min(min_dist, d)
                # 夹爪到位且闭合 -> 挂载，之后方块跟随（与采集时一致）
                closed = float(np.asarray(robot.get_joint_positions())[5]) > 0.8
                if not attached and d < args.grasp_dist and closed:
                    attached = True
                if attached:
                    data.qpos[cube_adr:cube_adr + 3] = gripper
                    mujoco.mj_forward(model, data)

            canvas = np.hstack([frames["front"], frames["wrist"]])
            label = f"step {i:03d}" + ("  [grasped]" if attached else "")
            cv2.putText(canvas, label, (10, 24),
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
    if dists:
        print(f"  末端-目标距离：最近 {min_dist * 100:.1f} cm，"
              f"末段均值 {np.mean(dists[-30:]) * 100:.1f} cm")
        print(f"  是否抓住：{'是' if attached else '否'}")


if __name__ == "__main__":
    main()
