"""命令行入口。"""

from __future__ import annotations

import argparse
import json
import os
import sys
import unicodedata

from . import __version__
from .diff import summarize_delta
from .model import REJECT_REASONS, Attempt, LedgerError
from .stats import format_stats, summarize, to_csv, export_rows
from .storage import Store


# ---------------------------------------------------------------- 显示辅助

def _width(text: str) -> int:
    """按终端显示宽度计算字符串长度（中日韩字符占两格）。"""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - _width(text))


def _outcome_label(attempt: Attempt) -> str:
    if attempt.outcome == "accepted":
        return "通过"
    if attempt.outcome == "rejected":
        label = REJECT_REASONS.get(attempt.reason, attempt.reason or "?")
        return "拒绝 · {}".format(label)
    return "待定"


# ---------------------------------------------------------------- 命令实现

def cmd_new(args, store: Store) -> int:
    ledger = store.load()
    shot = ledger.add_shot(args.shot_id, project=args.project, note=args.note)
    store.save(ledger)
    print("已创建镜头 {}".format(shot.id))
    return 0


def cmd_log(args, store: Store) -> int:
    ledger = store.load()

    if args.accept and args.reject:
        raise LedgerError("--accept 与 --reject 不能同时使用。")
    if args.reject and args.reject not in REJECT_REASONS:
        raise LedgerError(
            "未知的原因码 {!r}。可用：{}（`prompt-ledger reasons` 查看含义）".format(
                args.reject, ", ".join(REJECT_REASONS)
            )
        )

    if args.shot_id in ledger.shots:
        shot = ledger.shots[args.shot_id]
    else:
        shot = ledger.add_shot(args.shot_id, project=args.project, note=args.shot_note)
        print("（镜头 {} 不存在，已新建）".format(shot.id))

    outcome = "pending"
    reason = ""
    if args.accept:
        outcome = "accepted"
    elif args.reject:
        outcome = "rejected"
        reason = args.reject

    # 继承基准：--base 指定，或 --from-last 取最后一次
    base = None
    if args.from_last:
        base = shot.last()
        if base is None:
            raise LedgerError("这个镜头还没有任何记录，--from-last 无内容可继承。")
    elif args.base:
        base = shot.get(args.base)
        if base is None:
            raise LedgerError("镜头 {} 没有第 {} 次记录。".format(shot.id, args.base))

    prompt = args.prompt
    negative = args.negative
    model = args.model
    ratio = args.ratio
    seed = args.seed
    refs = list(args.ref or [])

    if base is not None:
        if prompt is None:
            prompt = base.prompt
        if negative is None:
            negative = base.negative
        if model is None:
            model = base.model
        if ratio is None:
            ratio = base.ratio
        if seed is None:
            seed = base.seed
        if not refs:
            refs = list(base.refs)

    if prompt is None:
        raise LedgerError(
            "缺少提示词。请用 --prompt 给出，或用 --from-last 继承上一次。"
        )

    change = ""
    if base is not None:
        change = summarize_delta(base.prompt, prompt)

    attempt = Attempt(
        n=shot.next_n(),
        prompt=prompt,
        negative=negative or "",
        model=model or "",
        ratio=ratio or "",
        seed=seed,
        refs=refs,
        outcome=outcome,
        reason=reason,
        note=args.note or "",
        based_on=base.n if base is not None else 0,
        change=change,
    )
    shot.attempts.append(attempt)

    if outcome == "accepted":
        _ensure_single_accepted(shot, attempt, force=False)

    store.save(ledger)

    print("已记录 {} 第 {} 次生成 · {}".format(shot.id, attempt.n, _outcome_label(attempt)))
    if change:
        print("  变化  {}".format(change))
    return 0


def _ensure_single_accepted(shot, attempt, force: bool) -> None:
    for other in shot.attempts:
        if other is attempt:
            continue
        if other.outcome == "accepted":
            if not force:
                raise LedgerError(
                    "镜头 {} 的第 {} 次已经是\"通过\"状态。\n"
                    "一个镜头只应有一个通过的版本；确要修改请加 --force。".format(
                        shot.id, other.n
                    )
                )
            other.outcome = "pending"


def cmd_accept(args, store: Store) -> int:
    ledger = store.load()
    shot = ledger.require(args.shot_id)
    attempt = _pick(shot, args.attempt)
    _ensure_single_accepted(shot, attempt, force=args.force)
    attempt.outcome = "accepted"
    attempt.reason = ""
    store.save(ledger)
    print("{} 第 {} 次标记为通过".format(shot.id, attempt.n))
    return 0


def cmd_reject(args, store: Store) -> int:
    ledger = store.load()
    shot = ledger.require(args.shot_id)
    if args.reason not in REJECT_REASONS:
        raise LedgerError(
            "--reason 只接受这些原因码：{}".format(", ".join(REJECT_REASONS))
        )
    attempt = _pick(shot, args.attempt)
    attempt.outcome = "rejected"
    attempt.reason = args.reason
    if args.note:
        attempt.note = args.note
    store.save(ledger)
    print("{} 第 {} 次标记为拒绝 · {}".format(
        shot.id, attempt.n, REJECT_REASONS[args.reason]))
    return 0


def _pick(shot, n):
    if n is None:
        attempt = shot.last()
        if attempt is None:
            raise LedgerError("镜头 {} 还没有任何记录。".format(shot.id))
        return attempt
    attempt = shot.get(n)
    if attempt is None:
        raise LedgerError("镜头 {} 没有第 {} 次记录。".format(shot.id, n))
    return attempt


def cmd_list(args, store: Store) -> int:
    ledger = store.load()
    if not ledger.shots:
        print("记录库是空的。用 `prompt-ledger new <镜头>` 开始。")
        return 0

    rows = [("镜头", "项目", "次数", "状态", "最近变化")]
    for shot in ledger.shots.values():
        accepted = shot.accepted()
        status = "通过 #{}".format(accepted.n) if accepted else "未通过"
        last_change = shot.attempts[-1].change if shot.attempts else ""
        rows.append((
            shot.id,
            shot.project,
            str(len(shot.attempts)),
            status,
            last_change,
        ))

    widths = [max(_width(r[i]) for r in rows) for i in range(len(rows[0]))]
    for index, row in enumerate(rows):
        line = "  ".join(_pad(cell, widths[i]) for i, cell in enumerate(row))
        print(line.rstrip())
        if index == 0:
            print("-" * min(_width(line), 100))
    return 0


def cmd_show(args, store: Store) -> int:
    ledger = store.load()
    shot = ledger.require(args.shot_id)

    header = shot.id
    if shot.project:
        header += "  " + shot.project
    if shot.note:
        header += "  · " + shot.note
    print(header)
    print("=" * max(_width(header), 40))

    if not shot.attempts:
        print("（还没有记录）")
        return 0

    for attempt in shot.attempts:
        meta = ["#{}".format(attempt.n), attempt.ts]
        if attempt.model:
            meta.append(attempt.model)
        if attempt.ratio:
            meta.append(attempt.ratio)
        print("  " + "  ".join(meta))
        print("    结果  " + _outcome_label(attempt))
        if attempt.prompt:
            print("    提示  " + attempt.prompt)
        if attempt.negative:
            print("    负向  " + attempt.negative)
        if attempt.seed is not None:
            print("    seed  {}".format(attempt.seed))
        if attempt.refs:
            print("    参考  " + ", ".join(attempt.refs))
        if attempt.change:
            print("    变化  " + attempt.change)
        if attempt.note:
            print("    备注  " + attempt.note)
        print()
    return 0


def cmd_stats(args, store: Store) -> int:
    ledger = store.load()
    print(format_stats(summarize(ledger)))
    return 0


def cmd_export(args, store: Store) -> int:
    ledger = store.load()
    if args.format == "csv":
        # utf-8-sig：Excel 直接双击打开中文不乱码
        text = to_csv(ledger)
        payload = ("﻿" if args.out else "") + text
    else:
        payload = json.dumps(export_rows(ledger), ensure_ascii=False, indent=2) + "\n"

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="") as handle:
            handle.write(payload)
        print("已导出 {} 条记录到 {}".format(len(export_rows(ledger)), args.out))
    else:
        sys.stdout.write(payload)
    return 0


def cmd_reasons(args, store: Store) -> int:
    for code, label in REJECT_REASONS.items():
        print("  {:<12} {}".format(code, label))
    return 0


# ---------------------------------------------------------------- 参数解析

def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--root",
        default=argparse.SUPPRESS,
        help="记录库目录（默认取 $PROMPT_LEDGER_HOME 或 ~/.prompt-ledger）",
    )

    parser = argparse.ArgumentParser(
        prog="prompt-ledger",
        description="记录 AI 生成内容的提示词迭代过程，并统计返工情况。",
        parents=[common],
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("new", parents=[common], help="新建一个镜头")
    p.add_argument("shot_id")
    p.add_argument("--project", default="", help="所属项目")
    p.add_argument("--note", default="", help="镜头说明")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("log", parents=[common], help="记录一次生成请求")
    p.add_argument("shot_id")
    p.add_argument("-p", "--prompt", default=None, help="提示词")
    p.add_argument("-n", "--negative", default=None, help="负向提示词")
    p.add_argument("-m", "--model", default=None, help="模型名")
    p.add_argument("-r", "--ratio", default=None, help="画面比例，如 9:16")
    p.add_argument("-s", "--seed", type=int, default=None, help="随机种子")
    p.add_argument("--ref", action="append", help="参考图路径，可重复")
    p.add_argument("--from-last", action="store_true",
                   help="继承上一次的提示词与参数，只覆盖你改动的部分")
    p.add_argument("--base", type=int, default=0,
                   help="以第 N 次为基准继承（默认 0 表示不继承）")
    p.add_argument("--note", default="", help="本次的备注")
    p.add_argument("--accept", action="store_true", help="直接标记为通过")
    p.add_argument("--reject", default=None, metavar="CODE",
                   help="直接标记为拒绝，并给出原因码")
    p.add_argument("--project", default="", help="镜头不存在时新建所用的项目名")
    p.add_argument("--shot-note", default="", help="镜头不存在时新建所用的说明")
    p.set_defaults(func=cmd_log)

    p = sub.add_parser("accept", parents=[common], help="把某次标记为通过")
    p.add_argument("shot_id")
    p.add_argument("--attempt", type=int, default=None, help="第几次（默认最后一次）")
    p.add_argument("--force", action="store_true", help="覆盖已经通过的版本")
    p.set_defaults(func=cmd_accept)

    p = sub.add_parser("reject", parents=[common], help="把某次标记为拒绝")
    p.add_argument("shot_id")
    p.add_argument("--attempt", type=int, default=None, help="第几次（默认最后一次）")
    p.add_argument("--reason", required=True, metavar="CODE", help="原因码")
    p.add_argument("--note", default="", help="补充说明")
    p.set_defaults(func=cmd_reject)

    p = sub.add_parser("list", parents=[common], help="列出所有镜头")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("show", parents=[common], help="查看一个镜头的全部尝试")
    p.add_argument("shot_id")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("stats", parents=[common], help="汇总统计")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("export", parents=[common], help="导出为 CSV 或 JSON")
    p.add_argument("-f", "--format", choices=["csv", "json"], default="csv")
    p.add_argument("-o", "--out", default=None, help="输出路径（默认打印到标准输出）")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("reasons", parents=[common], help="列出拒绝原因码")
    p.set_defaults(func=cmd_reasons)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    store = Store(root=getattr(args, "root", None))
    try:
        return args.func(args, store)
    except LedgerError as exc:
        print("错误：{}".format(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("已中断。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
