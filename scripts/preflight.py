#!/usr/bin/env python3
"""SO-101 仿真前置检查：参数对不对、方块够不够得着、相机看不看得见。

三项任一 FAIL 就不要往下采集或训练。

用法：
    MUJOCO_GL=egl python3 scripts/preflight.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "ros2_ws/src/voice_arm_core"
SCENE = CORE / "voice_arm/sim/assets/scene.xml"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

# SO-101 官方关节顺序与限位（弧度），来源 lerobot/robots/so_follower
EXPECT_JOINTS = [
    "shoulder_pan", "shoulder_lift", "elbow_flex",
    "wrist_flex", "wrist_roll", "gripper",
]
EXPECT_LIMITS = {
    "shoulder_pan": (-1.9199, 1.9199),
    "shoulder_lift": (-1.7453, 1.7453),
    "elbow_flex": (-1.69, 1.69),          # 模型带 5° 标定偏移
    "wrist_flex": (-1.6581, 1.6581),
    "wrist_roll": (-2.7438, 2.8412),
    "gripper": (-0.1745, 1.7453),
}

# 工作区（方块允许的随机范围），单位米
# 实测 x=0.48 一列全部不可达（末端最大伸展约 0.45 m），上界必须收到 0.44
GRID_X = (0.36, 0.44)
GRID_Y = (-0.09, 0.09)
IK_TOL = 0.005          # 5 mm
MIN_PIXEL_RATIO = 0.0015 # 方块至少占画面 0.15%（约 460 像素 @640x480）

CUBES = {
    "cube_green": ("绿", lambda b, g, r: (g > 150) & (r < 120) & (b < 120)),
    "cube_blue": ("蓝", lambda b, g, r: (b > 150) & (r < 120) & (g < 120)),
    "cube_red": ("红", lambda b, g, r: (r > 150) & (g < 100) & (b < 100)),
}


def fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")
    raise SystemExit(1)


def main() -> int:
    import mujoco

    from voice_arm.robot.sim import SimRobot
    from voice_arm.sim.kinematics import site_id, solve_ik

    print("SO-101 仿真前置检查")
    print("=" * 68)

    if not SCENE.exists():
        fail(f"场景不存在：{SCENE}")

    robot = SimRobot(image_size=(480, 640), xml_path=SCENE, cameras=("front", "wrist"))
    model, data = robot.model, robot.data
    if model is None:
        fail("MuJoCo 模型未加载（检查 MUJOCO_GL=egl）")

    # ---------- 1. 机械臂参数 ----------
    print("\n[1/3] 机械臂参数")
    joint_names = [
        mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, i)
        for i in range(model.njnt)
    ]
    arm_joints = joint_names[:6]
    if arm_joints != EXPECT_JOINTS:
        fail(f"关节顺序不符\n  期望 {EXPECT_JOINTS}\n  实际 {arm_joints}")
    print(f"  关节顺序 OK：{' → '.join(arm_joints)}")

    for i, name in enumerate(arm_joints):
        lo, hi = model.jnt_range[i]
        exp_lo, exp_hi = EXPECT_LIMITS[name]
        if abs(lo - exp_lo) > 0.02 or abs(hi - exp_hi) > 0.02:
            fail(f"{name} 限位不符：实际 [{lo:.4f}, {hi:.4f}]，期望 [{exp_lo}, {exp_hi}]")
    print("  六个关节限位与 SO-101 官方一致（容差 0.02 rad）")

    # ---------- 2. IK 可达性 ----------
    print("\n[2/3] 方块可达性（5x5 网格）")
    mujoco.mj_forward(model, data)
    xs = np.linspace(*GRID_X, 5)
    ys = np.linspace(*GRID_Y, 5)
    total = ok = 0
    worst = 0.0
    for x in xs:
        for y in ys:
            total += 1
            q, err = solve_ik(model, data, np.array([x, y, 0.10]), np.zeros(6),
                              target_z=(0.0, -0.5, -0.866))
            worst = max(worst, err)
            if err <= IK_TOL:
                ok += 1
    print(f"  可达 {ok}/{total}，最大误差 {worst * 1000:.1f} mm（容差 {IK_TOL * 1000:.0f} mm）")
    if ok != total:
        fail("工作区内有不可达点，缩小随机范围或把方块往臂根挪")

    # ---------- 3. 相机视野 ----------
    print("\n[3/3] 相机视野")
    frames = robot.get_frames()
    front = frames["front"]
    b, g, r = front[..., 0], front[..., 1], front[..., 2]

    yellow = ((r > 150) & (g > 120) & (b < 130)).mean()
    if yellow < 0.005:
        fail(f"画面里看不到机械臂（黄色占比 {yellow:.2%}），相机的 pos/xyaxes 可能不对")
    print(f"  机械臂可见：黄色占比 {yellow:.1%}")

    for body, (label, mask_fn) in CUBES.items():
        bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, body)
        if bid < 0:
            fail(f"场景里没有 {body}")
        ratio = mask_fn(b, g, r).mean()
        if ratio < MIN_PIXEL_RATIO:
            pos = np.round(data.xpos[bid], 3)
            fail(f"{label}色方块不可见（占比 {ratio:.2%}）@ {pos}，检查相机视野")
        # 是否落在画面中央 80%
        mask = mask_fn(b, g, r)
        ys_idx, xs_idx = np.nonzero(mask)
        cy, cx = ys_idx.mean() / front.shape[0], xs_idx.mean() / front.shape[1]
        edge = not (0.1 < cy < 0.9 and 0.1 < cx < 0.9)
        flag = "（贴边）" if edge else ""
        print(f"  {label}色方块可见：占比 {ratio:.2%}，画面位置 ({cx:.2f}, {cy:.2f}){flag}")

    print("\n" + "=" * 68)
    print("三项全部通过，可以进入采集/训练。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
