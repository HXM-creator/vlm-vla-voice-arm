#!/usr/bin/env python3
"""检查采集到的数据集：字段、形状、帧数、任务文本。

支持两种格式：
- npz 回退格式：目录下 episode_*.npz + meta.json
- LeRobotDataset v3：目录下有 meta/info.json

用法：
    python scripts/check_dataset.py --path outputs/datasets/sim_demo
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

EXPECTED_CAMERAS = ("front", "wrist")


def check_npz(root: Path) -> int:
    files = sorted(root.glob("episode_*.npz"))
    if not files:
        print(f"[FAIL] {root} 下没有 episode_*.npz")
        return 1

    meta_path = root / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}

    print(f"格式：npz    episode 数：{len(files)}")
    if meta:
        print(f"任务：{meta.get('task')}   fps：{meta.get('fps')}   相机：{meta.get('cameras')}")

    errors = 0
    total_frames = 0
    for f in files:
        with np.load(f) as d:
            keys = set(d.files)
            state = d["state"]
            action = d["action"]
            total_frames += state.shape[0]

            missing = {"state", "action", "front", "wrist"} - keys
            if missing:
                print(f"  [FAIL] {f.name} 缺字段：{sorted(missing)}")
                errors += 1
                continue

            if state.shape[0] != action.shape[0]:
                print(f"  [FAIL] {f.name} state/action 帧数不一致")
                errors += 1
            if state.shape[1] != 6:
                print(f"  [FAIL] {f.name} 关节数 {state.shape[1]}，期望 6")
                errors += 1
            if d["front"].shape != d["wrist"].shape:
                print(f"  [FAIL] {f.name} 两路相机形状不一致")
                errors += 1
            if not d["front"].dtype == np.uint8:
                print(f"  [FAIL] {f.name} 图像 dtype 应为 uint8")
                errors += 1

    print(f"总帧数：{total_frames}")
    if errors:
        print(f"\n[FAIL] {errors} 项不符合约定")
        return 1
    print("\n[OK] 字段、形状、相机数量均符合约定")
    return 0


def check_lerobot(root: Path) -> int:
    info_path = root / "meta" / "info.json"
    if not info_path.exists():
        print(f"[FAIL] {root} 不是 LeRobotDataset（缺 meta/info.json）")
        return 1
    info = json.loads(info_path.read_text(encoding="utf-8"))
    print("格式：LeRobotDataset v3")
    for k in ("robot_type", "total_episodes", "total_frames", "fps"):
        print(f"  {k}: {info.get(k)}")
    feats = info.get("features", {})
    cams = [k for k in feats if k.startswith("observation.images.")]
    print(f"  相机：{cams}")
    if len(cams) < 2:
        print("[FAIL] 相机数量少于 2，与双相机约定不符")
        return 1
    print("\n[OK] 数据集结构符合约定")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="检查数据集字段与形状")
    ap.add_argument("--path", required=True)
    args = ap.parse_args()
    root = Path(args.path)
    if not root.exists():
        print(f"[FAIL] 路径不存在：{root}")
        raise SystemExit(1)

    if (root / "meta" / "info.json").exists():
        code = check_lerobot(root)
    else:
        code = check_npz(root)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
