#!/usr/bin/env python3
"""验证语言条件是否真正生效。

方法：固定场景与初始关节角，只改变指令文本，比较两组动作轨迹。

判定逻辑：
- 两组动作几乎相同（平均欧氏距离 < 阈值）→ 语言条件未生效
- 两组动作明显不同 → 语言条件生效
- 策略未加载（动作为全零）→ 无法判断，输出 inconclusive，不冒充结论

用法：
    python scripts/check_language_conditioning.py \
        --checkpoint outputs/train/act/checkpoints/last \
        --instructions "pick up the green cube" "pick up the blue cube"

结果写入 outputs/lang_check/<timestamp>.json，可直接作为论文实验数据。
"""
from __future__ import annotations

import argparse
import json
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


def reset_scene(robot: SimRobot, dof: int = 6) -> np.ndarray:
    """把机械臂复位到固定初始姿态，保证两次实验的观测一致。"""
    q0 = np.zeros(dof, dtype=np.float32)
    robot.set_joint_positions(q0)
    robot.set_gripper(0.0)
    return q0


def rollout(policy: PolicyRunner, robot: SimRobot, instruction: str,
            steps: int) -> np.ndarray:
    """在固定场景下执行一条指令，返回逐步动作 (steps, dof)。"""
    reset_scene(robot, policy.dof)
    frames = robot.get_frames()  # 固定场景：只取一次，避免相机抖动干扰对比
    actions = []
    for _ in range(steps):
        act = policy.predict(frames, instruction)
        actions.append(np.asarray(act[0], dtype=np.float32))
    return np.stack(actions)


def compare(traj_a: np.ndarray, traj_b: np.ndarray) -> dict:
    """比较两组动作。"""
    if traj_a.shape != traj_b.shape:
        raise ValueError(f"shape mismatch: {traj_a.shape} vs {traj_b.shape}")

    per_step = np.linalg.norm(traj_a - traj_b, axis=1)
    return {
        "mean_distance": float(per_step.mean()),
        "max_distance": float(per_step.max()),
        "final_state_distance": float(np.linalg.norm(traj_a[-1] - traj_b[-1])),
        "per_step": [float(x) for x in per_step],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="语言条件验证")
    ap.add_argument("--checkpoint", default="", help="训练好的 checkpoint；为空则只能验证链路")
    ap.add_argument("--instructions", nargs="+", default=[
        "pick up the green cube",
        "pick up the blue cube",
    ])
    ap.add_argument("--steps", type=int, default=30)
    ap.add_argument("--threshold", type=float, default=0.01,
                    help="平均动作距离低于此值视为「未生效」")
    ap.add_argument("--image-size", default="480,640")
    ap.add_argument("--sim-xml", default="")
    ap.add_argument("--output", default="outputs/lang_check")
    args = ap.parse_args()

    if len(args.instructions) < 2:
        print("[FAIL] 至少需要两条指令才能做对比", file=sys.stderr)
        raise SystemExit(1)

    robot = SimRobot(dof=6, image_size=parse_size(args.image_size),
                     xml_path=args.sim_xml or None, cameras=("front", "wrist"))
    robot.connect()
    policy = PolicyRunner(checkpoint=args.checkpoint or None, action_chunk=1, dof=6)

    trajs = []
    for ins in args.instructions:
        traj = rollout(policy, robot, ins, args.steps)
        trajs.append(traj)
        print(f"指令：{ins!r}    动作范数均值={np.linalg.norm(traj, axis=1).mean():.4f}")

    robot.disconnect()

    comparisons = []
    for i in range(len(trajs)):
        for j in range(i + 1, len(trajs)):
            c = compare(trajs[i], trajs[j])
            c["pair"] = [args.instructions[i], args.instructions[j]]
            comparisons.append(c)

    any_motion = any(float(np.abs(t).max()) > 0 for t in trajs)

    if not any_motion:
        verdict = "inconclusive"
        reason = "所有动作为全零（策略未加载），无法判断语言条件是否生效"
    elif all(c["mean_distance"] < args.threshold for c in comparisons):
        verdict = "no_effect"
        reason = f"所有指令对的动作平均距离均 < {args.threshold}，模型很可能忽略了指令"
    else:
        verdict = "effective"
        reason = "不同指令产生了明显不同的动作，语言条件生效"

    result = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "checkpoint": args.checkpoint or None,
        "steps": args.steps,
        "threshold": args.threshold,
        "instructions": args.instructions,
        "action_norms": [float(np.linalg.norm(t, axis=1).mean()) for t in trajs],
        "comparisons": comparisons,
        "verdict": verdict,
        "reason": reason,
    }

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"lang_check_{time.strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 56)
    for c in comparisons:
        print(f"{c['pair'][0]}  vs  {c['pair'][1]}")
        print(f"  平均动作距离：{c['mean_distance']:.6f}")
        print(f"  最大动作距离：{c['max_distance']:.6f}")
    print("-" * 56)
    print(f"判定：{verdict}")
    print(f"说明：{reason}")
    print(f"结果已写入：{path}")

    # effective 与 inconclusive 都视为正常结束；只有明确「未生效」才以非零退出
    raise SystemExit(0 if verdict in ("effective", "inconclusive") else 2)


if __name__ == "__main__":
    main()
