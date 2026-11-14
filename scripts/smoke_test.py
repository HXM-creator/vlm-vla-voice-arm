#!/usr/bin/env python3
"""端到端冒烟：30 秒内回答“这套系统现在能不能用”。

依次检查：
1. 环境（mujoco / lerobot / opencv）
2. 渲染（MuJoCo 双相机出图，颜色通道正确）
3. 采集（IK 抓取轨迹 + 数据字段完整）
4. 推理（加载 checkpoint，动作在关节限位内）

用法：
    MUJOCO_GL=egl python3 scripts/smoke_test.py
    MUJOCO_GL=egl python3 scripts/smoke_test.py --checkpoint outputs/train/.../pretrained_model
    MUJOCO_GL=egl python3 scripts/smoke_test.py --skip-inference
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "ros2_ws/src/voice_arm_core"
SCENE = CORE / "voice_arm/sim/assets/scene.xml"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

RESULTS: list[tuple[bool, str, str]] = []


def check(name: str, fn) -> None:
    try:
        detail = fn() or ""
        RESULTS.append((True, name, str(detail)))
        print(f"  [OK  ] {name:<10s} {detail}")
    except Exception as exc:  # noqa: BLE001  冒烟脚本要汇总所有失败
        RESULTS.append((False, name, str(exc)))
        print(f"  [FAIL] {name:<10s} {exc}")


def check_env() -> str:
    import cv2
    import lerobot
    import mujoco

    return f"mujoco {mujoco.__version__} / lerobot {lerobot.__version__} / cv2 {cv2.__version__}"


def make_robot():
    from voice_arm.robot.sim import SimRobot

    if not SCENE.exists():
        raise FileNotFoundError(f"场景不存在：{SCENE}")
    robot = SimRobot(image_size=(240, 320), xml_path=SCENE, cameras=("front", "wrist"))
    if robot.model is None:
        raise RuntimeError("MuJoCo 模型未加载（检查 MUJOCO_GL）")
    return robot


def check_render() -> str:
    robot = make_robot()
    frames = robot.get_frames()
    for name in ("front", "wrist"):
        img = frames[name]
        if img.shape != (240, 320, 3):
            raise ValueError(f"{name} 形状异常：{img.shape}")
        if img.std() < 5:
            raise ValueError(f"{name} 画面几乎无变化（std={img.std():.1f}），可能没渲染出场景")
    # 黄色机械臂在 BGR 下约 (12, 210, 255)：用来验证颜色通道没反
    b, g, r = frames["front"][..., 0], frames["front"][..., 1], frames["front"][..., 2]
    yellow = float(((r > 150) & (g > 120) & (b < 130)).mean())
    if yellow < 0.005:
        raise ValueError(f"画面里找不到黄色机械臂（占比 {yellow:.2%}），颜色通道可能反了")
    return f"双相机 {frames['front'].shape}，黄色占比 {yellow:.1%}"


def check_record() -> str:
    import numpy as np

    from record_sim import collect_episode

    robot = make_robot()
    frames = collect_episode(
        robot, fps=30, duration_s=0.4, rng=np.random.default_rng(0),
        task="pick up the green cube",
    )
    if not frames:
        raise ValueError("采集返回空")
    f0 = frames[0]
    expect = {
        "observation.state", "action",
        "observation.images.front", "observation.images.wrist",
    }
    missing = expect - set(f0)
    if missing:
        raise ValueError(f"缺少字段：{sorted(missing)}")
    state = f0["observation.state"]
    if state.shape != (6,):
        raise ValueError(f"state 形状异常：{state.shape}")
    # 单位自检：弧度不应超过 2π
    if np.abs(state).max() > 2 * np.pi:
        raise ValueError(f"state 超出弧度范围：{np.abs(state).max():.2f}")
    # 动作应为下一帧状态（错位一帧）
    if not np.allclose(frames[0]["action"], frames[1]["observation.state"]):
        raise ValueError("action 与下一帧 state 不一致，错位逻辑有误")
    return f"{len(frames)} 帧，state 6 维，动作对齐正确"


def check_inference(checkpoint: str | None) -> str:
    from voice_arm.policy.runner import PolicyRunner

    if not checkpoint:
        return "跳过（未提供 --checkpoint）"
    ckpt = Path(checkpoint)
    if not ckpt.exists():
        raise FileNotFoundError(f"checkpoint 不存在：{ckpt}")

    robot = make_robot()
    runner = PolicyRunner(checkpoint=str(ckpt), dof=6, device="cpu")
    if runner.load_error:
        raise RuntimeError(runner.load_error)

    frames = robot.get_frames()
    action = runner.predict(frames, "pick up the green cube",
                            state=robot.get_joint_positions())
    if action.shape[1] != 6:
        raise ValueError(f"动作维度异常：{action.shape}")
    peak = float(np.abs(action).max())
    if peak > 3.15:                     # 弧度上限约 π
        raise ValueError(f"动作峰值 {peak:.2f} 超出弧度范围，单位可能错了")
    if peak < 1e-6:
        raise ValueError("动作全零，策略未生效")

    # 用关节限位再验一次（真实约束，比 3.15 更严格）
    model = robot.model
    limited = model.jnt_limited[:6].astype(bool)
    lo = np.where(limited, model.jnt_range[:6, 0], -np.inf)
    hi = np.where(limited, model.jnt_range[:6, 1], np.inf)
    over = float(np.max(np.maximum(lo - action, action - hi)))
    if over > 0.05:
        raise ValueError(f"动作超出关节限位 {over:.2f} rad")
    return f"单位 {runner._output_unit}，峰值 {peak:.2f} rad，未超限"


def main() -> int:
    ap = argparse.ArgumentParser(description="端到端冒烟测试")
    ap.add_argument("--checkpoint", default="", help="可选，给出则验证推理")
    ap.add_argument("--skip-inference", action="store_true")
    args = ap.parse_args()

    print("端到端冒烟")
    print("=" * 64)
    check("环境", check_env)
    check("渲染", check_render)
    check("采集", check_record)
    if args.skip_inference:
        print("  [SKIP] 推理       --skip-inference")
    else:
        check("推理", lambda: check_inference(args.checkpoint or None))

    failed = [r for r in RESULTS if not r[0]]
    print("=" * 64)
    if failed:
        print(f"失败 {len(failed)} 项：")
        for _, name, detail in failed:
            print(f"  - {name}: {detail}")
        return 1
    print("全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
