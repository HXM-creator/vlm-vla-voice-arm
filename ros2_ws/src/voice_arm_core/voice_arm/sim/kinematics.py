"""仿真侧的数值逆运动学。

用途：给定末端（gripperframe site）的目标世界坐标，解出 5 个臂关节角。
第 6 个关节是夹爪开合，不参与位置 IK。

方法：阻尼最小二乘（Levenberg-Marquardt 风格）
    dq = J^T (J J^T + λ²I)^-1 · e
比伪逆稳定，靠近奇异位形时不会炸。
"""
from __future__ import annotations

import numpy as np

ARM_DOF = 5                     # shoulder_pan / shoulder_lift / elbow_flex / wrist_flex / wrist_roll
GRIPPER_INDEX = 5               # 第 6 个关节是夹爪
SITE_NAME = "gripperframe"


def site_id(model) -> int:
    import mujoco

    sid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, SITE_NAME)
    if sid < 0:
        raise RuntimeError(f"模型里找不到 site \"{SITE_NAME}\"，检查 MJCF")
    return sid


def solve_ik(model, data, target, q_init, *, target_z=(0.0, 0.0, -1.0),
             iters: int = 400, damping: float = 0.08, step: float = 0.6,
             tol: float = 1e-3, ori_tol: float = 0.03,
             ori_weight: float = 0.3) -> tuple[np.ndarray, float]:
    """把末端解到 target（世界坐标 xyz），同时让夹爪 z 轴对准 target_z。

    只约束位置（3 自由度）时，5 个臂关节里剩下的 2 个由梯度路径决定，
    夹爪朝向会随机 —— 实测会朝天翘起、扣不住方块。所以这里同时约束
    3 个位置 + 3 个姿态分量，用超定最小二乘（6×5）求解。

    Returns:
        (q, pos_err)：q 为完整 qpos 前 6 维的拷贝，pos_err 为位置误差（米）
    """
    import mujoco

    sid = site_id(model)
    q = np.array(q_init[:6], dtype=np.float64, copy=True)
    q[GRIPPER_INDEX] = 0.0                      # IK 阶段夹爪全开
    lo = model.jnt_range[:6, 0]
    hi = model.jnt_range[:6, 1]
    target = np.asarray(target, dtype=np.float64)
    tz = np.asarray(target_z, dtype=np.float64)
    tz = tz / np.linalg.norm(tz)
    jacp = np.zeros((3, model.nv))
    jacr = np.zeros((3, model.nv))

    pos_err = np.zeros(3)
    for _ in range(iters):
        data.qpos[:6] = q[:6]
        mujoco.mj_forward(model, data)
        pos_err = target - data.site_xpos[sid]
        rot = data.site_xmat[sid].reshape(3, 3)
        ori_err = np.cross(rot[:, 2], tz)       # 夹爪 z 轴对准 tz
        if np.linalg.norm(pos_err) < tol and np.linalg.norm(ori_err) < ori_tol:
            break

        jacp[:] = 0.0
        jacr[:] = 0.0
        mujoco.mj_jacSite(model, data, jacp, jacr, sid)
        J = np.vstack([jacp[:, :ARM_DOF], jacr[:, :ARM_DOF]])
        e = np.concatenate([pos_err, ori_weight * ori_err])
        dq, *_ = np.linalg.lstsq(J, e, rcond=None)
        q[:ARM_DOF] = np.clip(q[:ARM_DOF] + step * dq, lo[:ARM_DOF], hi[:ARM_DOF])

    return q, float(np.linalg.norm(pos_err))


def cosine_interp(q_from: np.ndarray, q_to: np.ndarray, steps: int) -> np.ndarray:
    """两端速度为 0 的关节空间插值。"""
    if steps <= 0:
        return np.zeros((0, q_from.shape[0]), dtype=np.float32)
    s = 0.5 * (1 - np.cos(np.linspace(0.0, np.pi, steps)))
    return (1 - s)[:, None] * q_from[None, :] + s[:, None] * q_to[None, :]
