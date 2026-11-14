"""场景随机化：方块位置采样与写入。

采样不是纯随机，而是受几条物理约束：
1. 互不重叠：方块中心间距 ≥ MIN_GAP（对角线约 0.051 m，留余量）
2. 不贴边：限制在 preflight 验证过可达的工作区内
3. 均匀覆盖：在 2 cm 网格上采样，避免纯随机扎堆
4. 颜色解耦：调用方每条 episode 重新采样全部三块，使颜色与位置无关
"""
from __future__ import annotations

from itertools import combinations

import numpy as np

# 接口颜色 -> MuJoCo body 名
CUBE_BODIES = {
    "green": "cube_green",
    "blue": "cube_blue",
    "red": "cube_red",
}

# 工作区（scripts/preflight.py 验证：25/25 可达，误差 1 mm）
X_RANGE = (0.37, 0.43)
Y_RANGE = (-0.08, 0.08)
GRID_STEP = 0.01        # 1 cm 网格：候选点从 36 增到 119，避免布局重复
MIN_GAP = 0.07          # 方块中心最小间距（米）
CUBE_Z = 0.0182         # 半高 0.018 + 2 mm 间隙，落下即稳定


def _candidates() -> list[tuple[float, float]]:
    xs = np.arange(X_RANGE[0], X_RANGE[1] + 1e-9, GRID_STEP)
    ys = np.arange(Y_RANGE[0], Y_RANGE[1] + 1e-9, GRID_STEP)
    return [(round(float(x), 4), round(float(y), 4)) for x in xs for y in ys]


def sample_positions(rng: np.random.Generator,
                     n: int = 3) -> dict[str, tuple[float, float]]:
    """为 n 个方块采样互不重叠的位置，返回 {颜色: (x, y)}。"""
    pool = _candidates()
    if n > len(pool):
        raise ValueError(f"候选点不足：需要 {n}，只有 {len(pool)}")

    for _ in range(2000):
        idx = rng.choice(len(pool), size=n, replace=False)
        pts = [pool[i] for i in idx]
        gaps = [
            float(np.hypot(a[0] - b[0], a[1] - b[1]))
            for a, b in combinations(pts, 2)
        ]
        if min(gaps) >= MIN_GAP:
            colors = list(CUBE_BODIES)[:n]
            # 打乱颜色与位置的对应关系，保证两者不绑定
            order = rng.permutation(len(pts))
            return {colors[i]: pts[order[i]] for i in range(n)}

    raise RuntimeError(
        f"在 {n} 个方块、最小间距 {MIN_GAP} m 下找不到可行布局"
    )


def apply_positions(model, data,
                    positions: dict[str, tuple[float, float]]) -> None:
    """把方块搬到指定 (x, y)，保持 z 与朝向不变。"""
    import mujoco

    for color, (x, y) in positions.items():
        body = CUBE_BODIES[color]
        bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, body)
        if bid < 0:
            raise RuntimeError(f"场景里没有 {body}")
        adr = int(model.jnt_qposadr[model.body_jntadr[bid]])
        data.qpos[adr] = x
        data.qpos[adr + 1] = y
        data.qpos[adr + 2] = CUBE_Z
    mujoco.mj_forward(model, data)


def describe(positions: dict[str, tuple[float, float]]) -> str:
    """给日志用的一行摘要。"""
    parts = [f"{c}({p[0]:.2f}, {p[1]:+.2f})" for c, p in positions.items()]
    return " ".join(parts)
