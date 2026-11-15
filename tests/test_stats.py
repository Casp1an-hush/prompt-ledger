from prompt_ledger.model import Attempt, Ledger
from prompt_ledger.stats import export_rows, format_stats, summarize, to_csv


def build_ledger():
    ledger = Ledger()

    a = ledger.add_shot("S1", project="漫剧A")
    a.attempts = [
        Attempt(n=1, prompt="雨夜, 精致妆容", outcome="rejected", reason="expression"),
        Attempt(n=2, prompt="雨夜, 眼妆花掉", outcome="rejected", reason="expression"),
        Attempt(n=3, prompt="雨夜, 眼妆花掉, 鼻头发红", outcome="accepted"),
    ]

    b = ledger.add_shot("S2", project="漫剧A")
    b.attempts = [
        Attempt(n=1, prompt="对话, 中景", outcome="rejected", reason="consistency"),
        Attempt(n=2, prompt="对话, 中景, 站位图", outcome="accepted"),
    ]

    c = ledger.add_shot("S3", project="漫剧A")
    c.attempts = [Attempt(n=1, prompt="空镜", outcome="pending")]

    return ledger


def test_counts():
    stats = summarize(build_ledger())
    assert stats["shots_total"] == 3
    assert stats["shots_accepted"] == 2
    assert stats["shots_open"] == 1
    assert stats["attempts_total"] == 6


def test_iterations_to_accept():
    stats = summarize(build_ledger())
    assert stats["iterations_mean"] == 2.5  # 第 3 次 与 第 2 次
    assert stats["iterations_median"] == 2.5


def test_reject_reason_distribution():
    stats = summarize(build_ledger())
    assert stats["reject_reasons"]["expression"] == 2
    assert stats["reject_reasons"]["consistency"] == 1


def test_by_model_with_unspecified_bucket():
    ledger = build_ledger()
    stats = summarize(ledger)
    assert stats["by_model"]["(未指定)"]["attempts"] == 6


def test_empty_ledger():
    stats = summarize(Ledger())
    assert stats["iterations_mean"] is None
    assert "还没有标记为通过的镜头" in format_stats(stats)


def test_format_stats_mentions_labels():
    text = format_stats(summarize(build_ledger()))
    assert "平均第几次通过" in text
    assert "情绪或表演不对" in text


def test_export_rows_one_per_attempt():
    rows = export_rows(build_ledger())
    assert len(rows) == 6
    assert rows[0]["shot_id"] == "S1"
    assert rows[0]["attempt"] == 1


def test_csv_has_header_and_rows():
    text = to_csv(build_ledger())
    lines = text.strip().splitlines()
    assert lines[0].startswith("shot_id,project,shot_note")
    assert len(lines) == 7


def test_csv_escapes_commas_in_prompt():
    ledger = Ledger()
    shot = ledger.add_shot("S1")
    shot.attempts = [Attempt(n=1, prompt="a, b, c")]
    text = to_csv(ledger)
    assert '"a, b, c"' in text
