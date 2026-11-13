#!/usr/bin/env python3
"""在仿真中采集示教数据。

行为：
- 用 SimRobot 生成平滑的抓放轨迹（当前为关节空间余弦插值）
- 每帧同步记录双相机图像、关节角与下一帧动作
- 有 lerobot 时写入 LeRobotDataset v3；没有时回退为 .npz，保证任何环境可跑

用法：
    python scripts/record_sim.py --episodes 5 --fps 30 --duration 6 \
        --task "pick up the green cube" --output outputs/datasets/sim_demo

字段约定与 docs/architecture.md 一致：
    observation.state        (6,) float32   弧度
    action                   (6,) float32   下一帧目标关节角
    observation.images.front (H, W, 3) uint8
    observation.images.wrist (H, W, 3) uint8
    task                     str
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

# 允许直接跑脚本：把 src 加入路径
_SRC = Path(__file__).resolve().parents[1] / "ros2_ws" / "src" / "voice_arm_core"
if _SRC.exists() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from voice_arm.robot.sim import SimRobot  # noqa: E402

CAMERAS = ("front", "wrist")


def parse_size(text: str) -> tuple[int, int]:
    """'480,640' -> (480, 640)"""
    h, w = (int(x) for x in text.split(","))
    return h, w


def cosine_trajectory(q_start: np.ndarray, q_goal: np.ndarray, steps: int) -> np.ndarray:
    """余弦插值，两端速度为 0，比线性插值更接近真实示范。"""
    s = 0.5 * (1 - np.cos(np.linspace(0.0, np.pi, steps)))
    return (1 - s)[:, None] * q_start[None, :] + s[:, None] * q_goal[None, :]


def collect_episode(robot: SimRobot, fps: int, duration_s: float,
                    rng: np.random.Generator) -> list[dict]:
    """跑一条 episode，返回逐帧记录。"""
    steps = max(2, int(fps * duration_s))
    q_start = robot.get_joint_positions()
    # 随机目标：模拟物体位置变化带来的不同轨迹
    q_goal = q_start + rng.uniform(-0.6, 0.6, size=q_start.shape).astype(np.float32)
    q_goal = q_goal.astype(np.float32)

    traj = cosine_trajectory(q_start, q_goal, steps)

    frames: list[dict] = []
    prev_q = q_start.copy()
    for i in range(steps):
        q = traj[i].astype(np.float32)
        robot.set_joint_positions(q)
        robot.set_gripper(float(np.clip(0.5 + 0.5 * np.sin(i / steps * np.pi), 0, 1)))

        images = robot.get_frames()
        # 腕部相机未就绪时用 front 占位，保证字段固定
        wrist = images.get("wrist")
        front = images.get("front")
        if wrist is None and front is not None:
            wrist = front.copy()

        frames.append({
            "observation.state": q.copy(),
            "action": q.copy(),          # 下一步动作，最后由调用方错位一帧
            "observation.images.front": front,
            "observation.images.wrist": wrist,
        })
        prev_q = q

    # action[t] = state[t+1]，最后一帧复制自身
    for i in range(len(frames) - 1):
        frames[i]["action"] = frames[i + 1]["observation.state"].copy()
    frames[-1]["action"] = frames[-1]["observation.state"].copy()
    return frames


def write_npz(out_dir: Path, episodes: list[list[dict]], task: str, fps: int) -> Path:
    """无 lerobot 时的回退格式：一条 episode 一个 npz。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    for idx, frames in enumerate(episodes):
        path = out_dir / f"episode_{idx:04d}.npz"
        np.savez_compressed(
            path,
            state=np.stack([f["observation.state"] for f in frames]),
            action=np.stack([f["action"] for f in frames]),
            front=np.stack([f["observation.images.front"] for f in frames]),
            wrist=np.stack([f["observation.images.wrist"] for f in frames]),
            task=np.array(task),
            fps=np.array(fps),
        )
    meta = {"task": task, "fps": fps, "episodes": len(episodes),
            "format": "npz", "cameras": list(CAMERAS)}
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_dir


def write_lerobot(repo_id: str, root: Path, episodes: list[list[dict]],
                  task: str, fps: int, image_size: tuple[int, int]) -> Path:
    """写入 LeRobotDataset v3。接口与 lerobot-record 保持一致。"""
    from lerobot.datasets import LeRobotDataset

    h, w = image_size
    features = {
        "observation.state": {"dtype": "float32", "shape": (6,), "names": None},
        "action": {"dtype": "float32", "shape": (6,), "names": None},
        "observation.images.front": {"dtype": "video", "shape": (h, w, 3),
                                     "names": ["height", "width", "channels"]},
        "observation.images.wrist": {"dtype": "video", "shape": (h, w, 3),
                                     "names": ["height", "width", "channels"]},
    }

    dataset = LeRobotDataset.create(
        repo_id=repo_id, fps=fps, root=str(root),
        robot_type="so101_sim", features=features, use_videos=True,
    )
    for frames in episodes:
        for f in frames:
            dataset.add_frame({**f, "task": task})
        dataset.save_episode()
    dataset.finalize()  # 不调用会写出损坏的 parquet
    return root


def main() -> None:
    ap = argparse.ArgumentParser(description="仿真示教数据采集")
    ap.add_argument("--episodes", type=int, default=5)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--duration", type=float, default=6.0, help="单条 episode 秒数")
    ap.add_argument("--task", default="pick up the green cube",
                    help="训练用的英文任务模板，必须与推理时一致")
    ap.add_argument("--output", default="outputs/datasets/sim_demo")
    ap.add_argument("--repo-id", default="local/sim_demo")
    ap.add_argument("--image-size", default="480,640", help="高,宽")
    ap.add_argument("--sim-xml", default="", help="MuJoCo 场景 XML，留空用合成图像")
    ap.add_argument("--format", choices=["auto", "lerobot", "npz"], default="auto")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    image_size = parse_size(args.image_size)
    rng = np.random.default_rng(args.seed)

    robot = SimRobot(
        dof=6, image_size=image_size,
        xml_path=args.sim_xml or None, cameras=CAMERAS,
    )
    robot.connect()

    episodes: list[list[dict]] = []
    for i in range(args.episodes):
        frames = collect_episode(robot, args.fps, args.duration, rng)
        episodes.append(frames)
        print(f"episode {i}: {len(frames)} frames")

    robot.disconnect()

    out = Path(args.output)
    use_lerobot = args.format == "lerobot"
    if args.format == "auto":
        try:
            import lerobot  # noqa: F401
            use_lerobot = True
        except ImportError:
            use_lerobot = False

    if use_lerobot:
        try:
            path = write_lerobot(args.repo_id, out, episodes, args.task, args.fps, image_size)
            print(f"\n已写入 LeRobotDataset：{path}")
        except Exception as exc:  # noqa: BLE001  缺依赖或接口不兼容时回退
            print(f"[WARN] 写入 LeRobotDataset 失败（{exc}），回退为 npz")
            path = write_npz(out, episodes, args.task, args.fps)
            print(f"已写入 npz：{path}")
    else:
        path = write_npz(out, episodes, args.task, args.fps)
        print(f"\n已写入 npz：{path}")
        print("提示：安装 lerobot 后可产出 LeRobotDataset v3：pip install 'lerobot>=0.4'")

    total = sum(len(e) for e in episodes)
    print(f"合计 {args.episodes} 条 / {total} 帧 / {args.fps} fps / 任务：{args.task}")


if __name__ == "__main__":
    main()
