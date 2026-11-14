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


COLOR_TO_BODY = {"green": "cube_green", "blue": "cube_blue", "red": "cube_red"}

# 抓取轨迹各段占比：接近 / 下降 / 闭合 / 抬起 / 保持
SEGMENT_RATIOS = (0.33, 0.17, 0.08, 0.25, 0.17)
GRIPPER_OPEN = 0.0
GRIPPER_CLOSED = 1.5


def detect_target(task: str) -> tuple[str, str] | None:
    """从任务文本识别目标颜色，返回 (颜色, body 名)。"""
    lower = task.lower()
    for color, body in COLOR_TO_BODY.items():
        if color in lower:
            return color, body
    return None


def grasp_waypoints(robot: SimRobot, body_name: str) -> tuple[np.ndarray, ...]:
    """用 IK 解出 方块上方 / 方块处 / 抬起 三个关节位姿。"""
    import mujoco

    from voice_arm.sim.kinematics import solve_ik

    model, data = robot.model, robot.data
    bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, body_name)
    if bid < 0:
        raise RuntimeError(f"场景里没有 {body_name}")
    mujoco.mj_forward(model, data)
    cube = np.asarray(data.xpos[bid], dtype=np.float64).copy()

    q0 = robot.get_joint_positions().astype(np.float64)
    # SO-101 腕部行程有限（wrist_roll 实测会撞 -2.744 限位），从正上方垂直
    # 抓取不可达。真实使用也是斜着接近，这里把夹爪轴偏 30°。
    approach = np.array([0.0, -0.5, -0.866])
    q_above, e1 = solve_ik(model, data, cube + np.array([0, 0, 0.08]), q0,
                           target_z=approach)
    q_grasp, e2 = solve_ik(model, data, cube + np.array([0, 0, 0.02]), q_above,
                           target_z=approach)
    q_lift, e3 = solve_ik(model, data, cube + np.array([0, 0, 0.14]), q_grasp,
                          target_z=approach)
    print(f"    IK 误差: 上方 {e1 * 1000:.1f}mm / 抓取 {e2 * 1000:.1f}mm / 抬起 {e3 * 1000:.1f}mm")
    return q_above, q_grasp, q_lift


def collect_episode(robot: SimRobot, fps: int, duration_s: float,
                    rng: np.random.Generator, task: str) -> list[dict]:
    """跑一条 episode，返回逐帧记录。

    有 MuJoCo 模型且任务里能识别颜色时，用 IK 生成真实抓取轨迹；
    否则回退到原来的随机轨迹（保证无模型环境仍可跑通）。
    """
    steps = max(2, int(fps * duration_s))
    q_start = robot.get_joint_positions().astype(np.float64)
    target = detect_target(task)

    cube_adr = None
    cube_bid = None
    close_end = None
    site = None
    model = data = None

    if robot.model is not None and target is not None:
        import mujoco

        from voice_arm.sim.kinematics import site_id

        model, data = robot.model, robot.data
        # 每条 episode 重新摆放三个方块：位置随机、互不重叠、颜色与位置解耦
        from voice_arm.sim.scene import apply_positions, describe, sample_positions

        positions = sample_positions(rng)
        apply_positions(model, data, positions)
        print(f"    位置: {describe(positions)}")

        cube_bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, target[1])
        cube_adr = int(model.jnt_qposadr[model.body_jntadr[cube_bid]])
        site = site_id(model)

        q_above, q_grasp, q_lift = grasp_waypoints(robot, target[1])
        q_start[5] = GRIPPER_OPEN
        q_above[5] = GRIPPER_OPEN
        q_grasp[5] = GRIPPER_OPEN
        q_lift[5] = GRIPPER_CLOSED

        segs = [max(1, int(round(r * steps))) for r in SEGMENT_RATIOS]
        traj = np.vstack([
            cosine_trajectory(q_start, q_above, segs[0]),
            cosine_trajectory(q_above, q_grasp, segs[1]),
            cosine_trajectory(q_grasp, q_grasp, segs[2]),     # 闭合：位置不动
            cosine_trajectory(q_grasp, q_lift, segs[3]),
            cosine_trajectory(q_lift, q_lift, segs[4]),
        ])
        close_at = segs[0] + segs[1]
        traj[close_at:close_at + segs[2], 5] = np.linspace(
            GRIPPER_OPEN, GRIPPER_CLOSED, segs[2])
        traj[close_at + segs[2]:, 5] = GRIPPER_CLOSED
        close_end = close_at + segs[2]
    else:
        q_goal = q_start + rng.uniform(-0.6, 0.6, size=q_start.shape)
        traj = cosine_trajectory(q_start, q_goal, steps)

    frames: list[dict] = []
    cube_delta = None
    for i in range(min(steps, len(traj))):
        q = traj[i].astype(np.float32)
        robot.set_joint_positions(q)
        robot.set_gripper(float(np.clip(q[5], 0, 1)))

        # 运动学抓取：SimRobot 只做 mj_forward 不做 mj_step，夹爪闭合不会产生
        # 接触力，方块不会被带走。这里在闭合时刻记录方块相对夹爪的偏移，
        # 之后每帧把方块搬到夹爪上，使演示数据里真的“夹起来”。
        if cube_adr is not None:
            import mujoco

            mujoco.mj_forward(model, data)
            gripper_pos = np.asarray(data.site_xpos[site], dtype=np.float64)
            if cube_delta is None and i >= close_end - 1:
                cube_delta = np.asarray(data.xpos[cube_bid], dtype=np.float64) - gripper_pos
            if cube_delta is not None:
                data.qpos[cube_adr:cube_adr + 3] = gripper_pos + cube_delta
                mujoco.mj_forward(model, data)

        images = robot.get_frames()
        # 腕部相机未就绪时用 front 占位，保证字段固定
        wrist = images.get("wrist")
        front = images.get("front")
        if wrist is None and front is not None:
            wrist = front.copy()

        # SimRobot 按接口约定输出 BGR，lerobot 数据集约定 RGB，这里统一转换。
        # 不转会导致写入的视频通道反转：黄色机械臂变青色、蓝色地面变棕色。
        frames.append({
            "observation.state": q.copy(),
            "action": q.copy(),          # 下一步动作，最后由调用方错位一帧
            "observation.images.front": front[:, :, ::-1].copy(),
            "observation.images.wrist": wrist[:, :, ::-1].copy(),
        })

    # action[t] = state[t+1]，最后一帧复制自身
    for i in range(len(frames) - 1):
        frames[i]["action"] = frames[i + 1]["observation.state"].copy()
    frames[-1]["action"] = frames[-1]["observation.state"].copy()
    return frames


def write_npz(out_dir: Path, episodes: list[tuple[str, list[dict]]], fps: int) -> Path:
    """无 lerobot 时的回退格式：一条 episode 一个 npz。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    tasks_used = sorted({t for t, _ in episodes})
    for idx, (task, frames) in enumerate(episodes):
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
    meta = {"tasks": tasks_used, "fps": fps, "episodes": len(episodes),
            "format": "npz", "cameras": list(CAMERAS)}
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_dir


def write_lerobot(repo_id: str, root: Path, episodes: list[tuple[str, list[dict]]],
                  fps: int, image_size: tuple[int, int]) -> Path:
    """写入 LeRobotDataset v3。接口与 lerobot-record 保持一致。"""
    from lerobot.datasets.lerobot_dataset import LeRobotDataset

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
    for task, frames in episodes:
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
    ap.add_argument("--tasks", default="",
                    help="多任务，用 | 分隔；给了它则每个任务各采 --episodes 条")
    ap.add_argument("--output", default="outputs/datasets/sim_demo")
    ap.add_argument("--repo-id", default="local/sim_demo")
    ap.add_argument("--image-size", default="480,640", help="高,宽")
    ap.add_argument("--sim-xml", default="", help="MuJoCo 场景 XML，留空用合成图像")
    ap.add_argument("--format", choices=["auto", "lerobot", "npz"], default="auto")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--full-render", action="store_true",
                    help="保留阴影与反射（更真实，但渲染慢 3 倍）")
    args = ap.parse_args()

    image_size = parse_size(args.image_size)
    rng = np.random.default_rng(args.seed)

    robot = SimRobot(
        dof=6, image_size=image_size,
        xml_path=args.sim_xml or None, cameras=CAMERAS,
        fast_render=not args.full_render,
    )
    robot.connect()

    tasks = [t.strip() for t in args.tasks.split("|") if t.strip()] if args.tasks else [args.task]
    episodes: list[tuple[str, list[dict]]] = []
    for task in tasks:
        for i in range(args.episodes):
            frames = collect_episode(robot, args.fps, args.duration, rng, task)
            episodes.append((task, frames))
            print(f"[{task}] episode {i}: {len(frames)} frames")

    robot.disconnect()

    out = Path(args.output)
    use_lerobot = args.format == "lerobot"
    if args.format == "auto":
        try:
            import lerobot  # noqa: F401
            use_lerobot = True
        except ImportError:
            use_lerobot = False

    # 目录已存在时 LeRobotDataset.create 会抛 File exists 并静默回退 npz，
    # 让人误以为拿到了 lerobot 格式。这里提前拦住。
    if use_lerobot and out.exists() and any(out.iterdir()):
        raise SystemExit(
            f"输出目录已存在且非空：{out}\n"
            "请先删除它，或换一个 --output（lerobot 格式不会覆盖已有目录）"
        )

    if use_lerobot:
        try:
            path = write_lerobot(args.repo_id, out, episodes, args.fps, image_size)
            print(f"\n已写入 LeRobotDataset：{path}")
        except Exception as exc:  # noqa: BLE001
            # 显式要求 lerobot 格式时不再静默回退：npz 与 lerobot 结构不同，
            # 静默降级会让人以为数据格式正确，训练时才发现读不了。
            if args.format == "lerobot":
                raise SystemExit(f"写入 LeRobotDataset 失败：{exc}") from exc
            print(f"[WARN] 写入 LeRobotDataset 失败（{exc}），回退为 npz")
            path = write_npz(out, episodes, args.fps)
            print(f"已写入 npz：{path}")
    else:
        path = write_npz(out, episodes, args.fps)
        print(f"\n已写入 npz：{path}")
        print("提示：安装 lerobot 后可产出 LeRobotDataset v3：pip install 'lerobot>=0.4'")

    total = sum(len(frames) for _, frames in episodes)
    print(f"合计 {len(episodes)} 条 / {total} 帧 / {args.fps} fps / 任务：{tasks}")


if __name__ == "__main__":
    main()
