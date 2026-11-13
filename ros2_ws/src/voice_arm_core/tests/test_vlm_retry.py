"""VLM 客户端：重试、JSON 容错、失败抛出 VLMError。

不联网：用假的 OpenAI 客户端。
"""
import json
from types import SimpleNamespace

import pytest

from voice_arm.vlm.client import VLMClient, VLMError, _extract_json
from voice_arm.vlm.schema import Action


VALID = {
    "action": "pick",
    "target": {"color": "green", "shape": "cube"},
    "destination": {"region": "right"},
    "reply": "好的",
    "confidence": 0.9,
    "target_present": True,
    "position_hint": "left",
}


class FakeCompletions:
    def __init__(self, fail_times: int, content: str):
        self.calls = 0
        self.fail_times = fail_times
        self.content = content

    def create(self, **kwargs):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("simulated timeout")
        msg = SimpleNamespace(content=self.content)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def make_client(fail_times: int, content: str, max_retries: int = 1) -> VLMClient:
    client = VLMClient.__new__(VLMClient)  # 跳过 __init__，避免依赖 openai
    client.model = "fake"
    client.timeout_s = 15.0
    client.max_retries = max_retries
    fake = FakeCompletions(fail_times, content)
    client.client = SimpleNamespace(chat=SimpleNamespace(completions=fake))
    return client


def test_success_without_retry():
    c = make_client(0, json.dumps(VALID))
    cmd = c.parse("把绿色的方块抓起来", "b64")
    assert cmd.action is Action.PICK
    assert c.client.chat.completions.calls == 1


def test_retry_once_then_success():
    c = make_client(1, json.dumps(VALID))
    cmd = c.parse("把绿色的方块抓起来", "b64")
    assert cmd.action is Action.PICK
    assert c.client.chat.completions.calls == 2


def test_all_retries_fail_raises():
    c = make_client(5, json.dumps(VALID), max_retries=1)
    with pytest.raises(VLMError):
        c.parse("把绿色的方块抓起来", "b64")
    assert c.client.chat.completions.calls == 2


def test_invalid_json_retried_then_raises():
    c = make_client(0, "这不是 JSON", max_retries=1)
    with pytest.raises(VLMError):
        c.parse("把绿色的方块抓起来", "b64")


def test_extract_json_with_code_fence():
    raw = '```json\n{"action": "pick"}\n```'
    assert _extract_json(raw) == {"action": "pick"}


def test_extract_json_with_surrounding_text():
    raw = '好的，结果如下：{"action": "pick"} 以上。'
    assert _extract_json(raw) == {"action": "pick"}


def test_extract_json_raises_on_garbage():
    with pytest.raises(VLMError):
        _extract_json("完全没有对象")
