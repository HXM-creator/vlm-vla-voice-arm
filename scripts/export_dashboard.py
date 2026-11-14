#!/usr/bin/env python3
"""把回放与语言条件结果导出成看板数据。

输出 outputs/dashboard/data.js —— 写成 JS 赋值而不是 JSON，
因为双击打开 HTML 时 file:// 协议下 fetch .json 会被 CORS 拦。
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs" / "dashboard"
TEMPLATE = ROOT / "dashboard" / "index.html"


def read_summary(path: Path) -> dict:
    """解析 summary.txt 里的 key: value 行。"""
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            data[key.strip()] = value.strip()
    return data


def load_replay() -> dict | None:
    npz = ROOT / "outputs/replay/replay.npz"
    if not npz.exists():
        return None
    d = np.load(npz)
    summary = read_summary(npz.with_name("summary.txt"))
    return {
        "steps": int(d["actions"].shape[0]),
        "actions": np.round(d["actions"], 6).tolist(),
        "states": np.round(d["states"], 6).tolist(),
        "summary": summary,
    }


def load_lang() -> dict | None:
    files = sorted((ROOT / "outputs/lang_check").glob("lang_check_*.json"))
    if not files:
        return None
    # 优先展示 effective 的结果：全零的 inconclusive 是失败运行，不该盖掉有效结果
    parsed = [(p, json.loads(p.read_text(encoding="utf-8"))) for p in files]
    effective = [item for item in parsed if item[1].get("verdict") == "effective"]
    newest, raw = max(effective or parsed, key=lambda item: item[0].stat().st_mtime)
    return {
        "file": newest.name,
        "timestamp": raw.get("timestamp"),
        "steps": raw.get("steps"),
        "threshold": raw.get("threshold"),
        "verdict": raw.get("verdict"),
        "instructions": raw.get("instructions", []),
        "action_norms": raw.get("action_norms", []),
        "comparisons": [
            {
                "pair": c.get("pair"),
                "mean_distance": c.get("mean_distance"),
                "max_distance": c.get("max_distance"),
                "per_step": c.get("per_step", []),
            }
            for c in raw.get("comparisons", [])
        ],
    }


def main() -> None:
    payload = {"replay": load_replay(), "lang": load_lang()}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUT_DIR / "data.js"
    body = json.dumps(payload, ensure_ascii=False, indent=None)
    target.write_text(f"window.DASHBOARD = {body};\n", encoding="utf-8")
    if TEMPLATE.exists():
        shutil.copy(TEMPLATE, OUT_DIR / "index.html")
    print(f"已写入 {target}")
    print(f"打开看板: file://{OUT_DIR / 'index.html'}")
    replay = payload["replay"]
    lang = payload["lang"]
    print(f"  回放: {replay['steps'] if replay else 0} 步")
    print(f"  语言条件: {lang['verdict'] if lang else '无'}（{lang['file'] if lang else '-'}）")


if __name__ == "__main__":
    main()
