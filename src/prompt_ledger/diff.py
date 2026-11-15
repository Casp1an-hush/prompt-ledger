"""提示词版本之间的差异。

为什么不直接做字符级 diff？

提示词在实践中是一串以逗号分隔的短语（"雨夜, 特写, 精致妆容, 柔光"）。
真正有意义的迭代信息是"哪几个短语被拿掉了、加了什么"，而不是
"第 37 个字符变了"。所以这里按短语切分，比较短语集合。
"""

from __future__ import annotations

import re

_SEPARATORS = re.compile(r"[,，、;；\n]+")


def tokenize(prompt: str) -> list:
    """把提示词切成短语列表，保持原有顺序。"""
    if not prompt:
        return []
    parts = (p.strip() for p in _SEPARATORS.split(prompt))
    return [p for p in parts if p]


def prompt_delta(old: str, new: str):
    """返回 (added, removed)，各自按在对应文本中出现的顺序排列。"""
    old_tokens = tokenize(old)
    new_tokens = tokenize(new)
    removed = [t for t in old_tokens if t not in new_tokens]
    added = [t for t in new_tokens if t not in old_tokens]
    return added, removed


def summarize_delta(old: str, new: str) -> str:
    """生成一行可读的变化摘要，供记录库与导出使用。"""
    added, removed = prompt_delta(old, new)

    if not added and not removed:
        if (old or "").strip() == (new or "").strip():
            return ""
        return "无明显短语变化"

    bits = []
    if added:
        bits.append("+ " + " / ".join(added))
    if removed:
        bits.append("- " + " / ".join(removed))
    return "；".join(bits)
