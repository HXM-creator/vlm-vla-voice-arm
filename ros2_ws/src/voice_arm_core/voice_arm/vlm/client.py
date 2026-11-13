"""VLM 客户端：把中文口语转成固定模板的英文任务指令。

职责边界见 docs/architecture.md：
- 只做翻译、目标存在性确认、粗略方位描述
- 不输出坐标，方位不进入 VLA 输入

用法：
    from voice_arm.vlm.client import VLMClient
    client = VLMClient()
    cmd = client.parse("把绿色的方块抓起来", image_b64)

命令行试用：
    python -m voice_arm.vlm.client --image desk.jpg --text "把绿色的方块抓起来"
"""
from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from .prompts import SYSTEM_PROMPT, build_user_prompt
from .schema import Command, SchemaError, validate

log = logging.getLogger(__name__)

DEFAULT_MODEL = "deepseek-flash"
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_TIMEOUT_S = 15.0
DEFAULT_MAX_RETRIES = 1

_CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class VLMError(RuntimeError):
    """调用或解析失败。"""


def _extract_json(text: str) -> dict[str, Any]:
    """从模型输出中取出 JSON，兼容 ```json 包裹与前后解释文字。"""
    if not text:
        raise VLMError("empty response")

    cleaned = _CODE_FENCE.sub("", text).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 退一步：截取第一个 { 到最后一个 }
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise VLMError(f"invalid json: {exc}") from exc

    raise VLMError(f"no json object in response: {cleaned[:120]}")


class VLMClient:
    """OpenAI 兼容接口的视觉语言模型客户端。"""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ):
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise VLMError(
                "未安装 openai。安装：pip install 'openai>=1.30'"
            ) from exc

        key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        if not key:
            raise VLMError(
                "缺少 API Key。设置环境变量 DEEPSEEK_API_KEY，"
                "不要把 key 写进代码或配置文件。"
            )

        self.model = model
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        # OpenAI SDK 自带超时；这里显式传，避免默认值过长
        self.client = OpenAI(api_key=key, base_url=base_url, timeout=timeout_s)

    # ---------- 核心 ----------
    def parse(self, instruction: str, image_b64: str) -> Command:
        """把中文指令与桌面图像解析为 Command。

        Raises:
            VLMError: 所有重试都失败
        """
        last_err: Exception | None = None

        for attempt in range(self.max_retries + 1):
            started = time.monotonic()
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": build_user_prompt(instruction)},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                                },
                            ],
                        },
                    ],
                    temperature=0.0,
                )
                elapsed = time.monotonic() - started
                raw = _extract_json(resp.choices[0].message.content or "")
                cmd = validate(raw)
                log.info("vlm ok in %.2fs (attempt %d)", elapsed, attempt + 1)
                return cmd

            except (VLMError, SchemaError, json.JSONDecodeError) as exc:
                last_err = exc
                log.warning("vlm parse failed (attempt %d): %s", attempt + 1, exc)
            except Exception as exc:  # noqa: BLE001  网络、超时、鉴权
                last_err = exc
                log.warning("vlm request failed (attempt %d): %s", attempt + 1, exc)

        raise VLMError(f"VLM 解析失败，已重试 {self.max_retries} 次：{last_err}") from last_err

    # ---------- 便捷构造 ----------
    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> "VLMClient":
        v = cfg.get("vlm", {})
        return cls(
            model=v.get("model", DEFAULT_MODEL),
            base_url=v.get("base_url", DEFAULT_BASE_URL),
            timeout_s=float(v.get("timeout_s", DEFAULT_TIMEOUT_S)),
            max_retries=int(v.get("max_retries", DEFAULT_MAX_RETRIES)),
        )


def _encode_image(path: str) -> str:
    p = Path(path)
    if not p.exists():
        raise VLMError(f"图片不存在：{path}")
    return base64.b64encode(p.read_bytes()).decode()


def main() -> None:
    ap = argparse.ArgumentParser(description="VLM 单次试用：中文指令 + 桌面图 -> 结构化指令")
    ap.add_argument("--image", required=True, help="桌面图像路径")
    ap.add_argument("--text", required=True, help="中文指令")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    ap.add_argument("--raw", action="store_true", help="同时输出完整 Command 字段")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)-7s | %(message)s",
        stream=sys.stdout,
    )

    try:
        client = VLMClient(model=args.model, base_url=args.base_url, timeout_s=args.timeout)
        b64 = _encode_image(args.image)
        started = time.monotonic()
        cmd = client.parse(args.text, b64)
        elapsed = time.monotonic() - started
    except VLMError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(f"\n指令：{args.text}")
    print(f"VLA 将收到：{cmd.to_vla_instruction()}")
    print(f"目标存在：{cmd.target_present}")
    print(f"方位（仅对话）：{cmd.position_hint}")
    print(f"语音回复：{cmd.reply}")
    print(f"耗时：{elapsed:.2f} s")

    if args.raw:
        print("\n完整字段：")
        print(json.dumps(cmd.__dict__, default=str, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
