#!/usr/bin/env python3
"""在仿真中回放策略，记录动作曲线用于检查。

无 checkpoint 时使用 PolicyRunner 的零动作回退，仍可跑通链路并产出曲线，
方便在训练前验证数据流与频率。

用法：
    python scripts/replay_sim.py --steps 200
    python scripts/replay_sim.py --checkpoint outputs/train/act/checkpoints/last
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

_SRC = Path(__file__).resolve().parents[1] / "ros2_ws" / "src" / "voice_arm_core"
if _SRC.exists() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from voice_arm.policy.runner import PolicyRunner  # noqa: E402
from voice_arm.robot.sim import SimRobot  # noqa: E402


def parse_size(text: str) -> tuple[int, int]:
    h, w = (int(x) for x in text.split(","))
    return h, w


def main() -> None:
    ap = argparse.ArgumentParser(description="仿真回放策略并记录动作曲线")
    ap.add_argument("--checkpoint", default="", help="训练好的 checkpoint 目录，留空则用零动作")
    ap.add_argument("--steps", type=int, default=200)
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--image-size", default="480,640")
    ap.add_argument("--sim-xml", default="")
    ap.add_argument("--output", default="outputs/replay")
    args = ap.parse_args()

    robot = SimRobot(dof=6, image_size=parse_size(args.image_size),
                     xml_path=args.sim_xml or None, cameras=("front", "wrist"))
    robot.connect()
    policy = PolicyRunner(checkpoint=args.checkpoint or None, action_chunk=1, dof=6)

    actions: list[np.ndarray] = []
    states: list[np.ndarray] = []
    period = 1.0 / args.fps
    started = time.monotonic()

    for i in range(args.steps):
        loop_start = time.monotonic()
        frames = robot.get_frames()
        act = policy.predict(frames, instruction="pick up the green cube")
        q = act[0]
        robot.set_joint_positions(q)
        actions.append(np.asarray(q, dtype=np.float32))
        states.append(robot.get_joint_positions())

        rest = period - (time.monotonic() - loop_start)
        if rest > 0:
            time.sleep(rest)

    robot.disconnect()
    elapsed = time.monotonic() - started

    A = np.stack(actions)
    S = np.stack(states)
    delta = np.abs(np.diff(A, axis=0)) if len(A) > 1 else np.zeros((0, A.shape[1]))

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out / "replay.npz", actions=A, states=S)
    (out / "summary.txt").write_text(
        "\n".join([
            f"steps: {len(A)}",
            f"fps: {args.fps:.1f}",
            f"wall_time_s: {elapsed:.2f}",
            f"actual_fps: {len(A) / elapsed:.1f}",
            f"action_mean: {A.mean():.4f}",
            f"action_std: {A.std():.4f}",
            f"mean_abs_delta: {delta.mean() if delta.size else 0.0:.6f}",
            f"checkpoint: {args.checkpoint or '(none, zero actions)'}",
        ]) + "\n",
        encoding="utf-8",
    )

    print(f"steps={len(A)}  actual_fps={len(A)/elapsed:.1f}  "
          f"action_std={A.std():.4f}  mean_abs_delta={delta.mean() if delta.size else 0.0:.6f}")
    print(f"已写入：{out / 'replay.npz'} 与 summary.txt")
    if not args.checkpoint:
        print("提示：未提供 --checkpoint，使用零动作回退，仅用于验证链路与频率。")


if __name__ == "__main__":
    main()
