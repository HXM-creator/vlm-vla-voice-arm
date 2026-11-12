"""VLM 客户端：调用视觉语言模型并校验输出。"""
from __future__ import annotations

import json
import logging
import os

from .prompts import SYSTEM_PROMPT, build_user_prompt
from .schema import Command, SchemaError, validate

log = logging.getLogger(__name__)


class VLMClient:
    """OpenAI 兼容接口的 VLM 客户端。"""

    def __init__(self, model: str = "deepseek-flash",
                 base_url: str = "https://api.deepseek.com",
                 api_key: str | None = None, max_retries: int = 1):
        from openai import OpenAI

        self.model = model
        self.max_retries = max_retries
        self.client = OpenAI(
            api_key=api_key or os.environ.get("DEEPSEEK_API_KEY", ""),
            base_url=base_url,
        )

    def parse(self, instruction: str, image_b64: str) -> Command:
        """把指令与图像解析为 Command。解析失败时重试一次。"""
        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": [
                            {"type": "text", "text": build_user_prompt(instruction)},
                            {"type": "image_url",
                             "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                        ]},
                    ],
                    temperature=0.0,
                )
                raw = json.loads(resp.choices[0].message.content)
                return validate(raw)
            except (json.JSONDecodeError, SchemaError) as exc:
                last_err = exc
                log.warning("parse failed (attempt %d): %s", attempt + 1, exc)
        raise RuntimeError(f"VLM 解析失败：{last_err}")
