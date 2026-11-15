"""统计与导出。"""

from __future__ import annotations

import csv
import io
from collections import Counter

from .model import REJECT_REASONS, Ledger


def _median(values):
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def summarize(ledger: Ledger) -> dict:
    """把记录库压缩成一组可比较的指标。

    `iterations_to_accept` 是我们最关心的量：一个镜头在第几次尝试才通过。
    它衡量的是"手感"——说得更准确一点，是运气在多大程度上支配了产出。
    """
    shots = list(ledger.shots.values())
    attempts = [a for s in shots for a in s.attempts]

    accepted_shots = [s for s in shots if s.accepted() is not None]
    iterations = [s.accepted().n for s in accepted_shots]

    reasons = Counter(
        a.reason for a in attempts if a.outcome == "rejected" and a.reason
    )

    by_model = {}
    for attempt in attempts:
        key = attempt.model or "(未指定)"
        bucket = by_model.setdefault(key, {"attempts": 0, "rejected": 0})
        bucket["attempts"] += 1
        if attempt.outcome == "rejected":
            bucket["rejected"] += 1

    return {
        "shots_total": len(shots),
        "shots_accepted": len(accepted_shots),
        "shots_open": len(shots) - len(accepted_shots),
        "attempts_total": len(attempts),
        "iterations_mean": (
            sum(iterations) / len(iterations) if iterations else None
        ),
        "iterations_median": _median(iterations),
        "reject_reasons": reasons,
        "by_model": by_model,
    }


def format_stats(stats: dict) -> str:
    lines = []
    lines.append("镜头总数      {}".format(stats["shots_total"]))
    lines.append("已通过        {}".format(stats["shots_accepted"]))
    lines.append("未通过        {}".format(stats["shots_open"]))
    lines.append("生成请求总数  {}".format(stats["attempts_total"]))

    if stats["iterations_mean"] is not None:
        lines.append("")
        lines.append("平均第几次通过  {:.2f}".format(stats["iterations_mean"]))
        lines.append("中位第几次通过  {:g}".format(stats["iterations_median"]))
    else:
        lines.append("")
        lines.append("（还没有标记为通过的镜头）")

    if stats["reject_reasons"]:
        lines.append("")
        lines.append("拒绝原因分布")
        for code, count in stats["reject_reasons"].most_common():
            label = REJECT_REASONS.get(code, code)
            lines.append("  {:<12} {:>4}  {}".format(code, count, label))

    if stats["by_model"]:
        lines.append("")
        lines.append("按模型")
        for model, bucket in sorted(stats["by_model"].items()):
            lines.append(
                "  {:<20} 请求 {:>4}  被拒 {:>4}".format(
                    model, bucket["attempts"], bucket["rejected"]
                )
            )

    return "\n".join(lines)


EXPORT_FIELDS = [
    "shot_id",
    "project",
    "shot_note",
    "attempt",
    "ts",
    "model",
    "ratio",
    "seed",
    "prompt",
    "negative",
    "refs",
    "outcome",
    "reason",
    "note",
    "change",
    "based_on",
]


def export_rows(ledger: Ledger) -> list:
    """把每条 attempt 摊平为一行，便于导入 pandas 或 Excel。"""
    rows = []
    for shot in ledger.shots.values():
        for attempt in shot.attempts:
            rows.append(
                {
                    "shot_id": shot.id,
                    "project": shot.project,
                    "shot_note": shot.note,
                    "attempt": attempt.n,
                    "ts": attempt.ts,
                    "model": attempt.model,
                    "ratio": attempt.ratio,
                    "seed": "" if attempt.seed is None else attempt.seed,
                    "prompt": attempt.prompt,
                    "negative": attempt.negative,
                    "refs": "|".join(attempt.refs),
                    "outcome": attempt.outcome,
                    "reason": attempt.reason,
                    "note": attempt.note,
                    "change": attempt.change,
                    "based_on": attempt.based_on,
                }
            )
    return rows


def to_csv(ledger: Ledger) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=EXPORT_FIELDS)
    writer.writeheader()
    for row in export_rows(ledger):
        writer.writerow(row)
    return buffer.getvalue()
