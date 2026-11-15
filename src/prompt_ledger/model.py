"""数据模型：镜头 (Shot) 与生成尝试 (Attempt)。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

# 受控的拒绝原因词表。
#
# 自由文本的拒绝理由无法统计，而"为什么被拒"恰恰是迭代路径里信息量最大的
# 一环。用一组有限的原因码，才能回答"这个团队最常在哪一类问题上返工"。
REJECT_REASONS = {
    "consistency": "角色／场景前后不一致",
    "expression": "情绪或表演不对",
    "composition": "构图、机位或景别不对",
    "artifact": "画面崩坏、穿帮或畸形",
    "style": "画风偏移或风格不统一",
    "text": "文字、字幕或符号错误",
    "pacing": "节奏、时长或运镜不对",
    "other": "其他",
}

OUTCOMES = ("pending", "accepted", "rejected")


class LedgerError(Exception):
    """面向用户的、可直接展示的错误。"""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class Attempt:
    """一次生成请求。这是本工具记录的最小单位。"""

    n: int
    prompt: str = ""
    negative: str = ""
    model: str = ""
    ratio: str = ""
    seed: int | None = None
    refs: list = field(default_factory=list)
    outcome: str = "pending"
    reason: str = ""
    note: str = ""
    based_on: int = 0
    change: str = ""
    ts: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        return {
            "n": self.n,
            "prompt": self.prompt,
            "negative": self.negative,
            "model": self.model,
            "ratio": self.ratio,
            "seed": self.seed,
            "refs": list(self.refs),
            "outcome": self.outcome,
            "reason": self.reason,
            "note": self.note,
            "based_on": self.based_on,
            "change": self.change,
            "ts": self.ts,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Attempt":
        return cls(
            n=int(data["n"]),
            prompt=data.get("prompt", ""),
            negative=data.get("negative", ""),
            model=data.get("model", ""),
            ratio=data.get("ratio", ""),
            seed=data.get("seed"),
            refs=list(data.get("refs") or []),
            outcome=data.get("outcome", "pending"),
            reason=data.get("reason", ""),
            note=data.get("note", ""),
            based_on=int(data.get("based_on") or 0),
            change=data.get("change", ""),
            ts=data.get("ts", ""),
        )


@dataclass
class Shot:
    """一个镜头（或任意一个独立的内容单元），下挂它的全部生成尝试。"""

    id: str
    project: str = ""
    note: str = ""
    created: str = field(default_factory=_now)
    attempts: list = field(default_factory=list)

    def next_n(self) -> int:
        return max((a.n for a in self.attempts), default=0) + 1

    def last(self):
        return self.attempts[-1] if self.attempts else None

    def get(self, n: int):
        for a in self.attempts:
            if a.n == n:
                return a
        return None

    def accepted(self):
        for a in self.attempts:
            if a.outcome == "accepted":
                return a
        return None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project": self.project,
            "note": self.note,
            "created": self.created,
            "attempts": [a.to_dict() for a in self.attempts],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Shot":
        return cls(
            id=data["id"],
            project=data.get("project", ""),
            note=data.get("note", ""),
            created=data.get("created", ""),
            attempts=[Attempt.from_dict(a) for a in data.get("attempts") or []],
        )


@dataclass
class Ledger:
    """整个记录库。"""

    schema: int = 1
    shots: dict = field(default_factory=dict)

    def add_shot(self, shot_id: str, project: str = "", note: str = "") -> Shot:
        if shot_id in self.shots:
            raise LedgerError("镜头 {} 已存在。".format(shot_id))
        shot = Shot(id=shot_id, project=project, note=note)
        self.shots[shot_id] = shot
        return shot

    def require(self, shot_id: str) -> Shot:
        if shot_id not in self.shots:
            raise LedgerError(
                "没有找到镜头 {}。先用 `prompt-ledger new {}` 创建，"
                "或在 log 时省略该检查。".format(shot_id, shot_id)
            )
        return self.shots[shot_id]

    def to_dict(self) -> dict:
        return {
            "schema": self.schema,
            "shots": [s.to_dict() for s in self.shots.values()],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Ledger":
        schema = int(data.get("schema", 1))
        if schema != 1:
            raise LedgerError(
                "记录库版本为 {}，本版本程序只认识版本 1。".format(schema)
            )
        ledger = cls(schema=schema)
        for item in data.get("shots") or []:
            shot = Shot.from_dict(item)
            ledger.shots[shot.id] = shot
        return ledger
