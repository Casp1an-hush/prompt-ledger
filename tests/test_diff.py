from prompt_ledger.diff import prompt_delta, summarize_delta, tokenize


def test_tokenize_handles_chinese_and_english_separators():
    assert tokenize("雨夜, 特写，精致妆容、柔光") == ["雨夜", "特写", "精致妆容", "柔光"]


def test_tokenize_ignores_empty_pieces():
    assert tokenize("a,,b,,") == ["a", "b"]
    assert tokenize("  ") == []


def test_tokenize_empty_input():
    assert tokenize("") == []
    assert tokenize(None) == []


def test_prompt_delta_reports_both_sides():
    old = "雨夜, 特写, 精致妆容, 柔光"
    new = "雨夜, 特写, 眼妆花掉, 鼻头发红"
    added, removed = prompt_delta(old, new)
    assert added == ["眼妆花掉", "鼻头发红"]
    assert removed == ["精致妆容", "柔光"]


def test_prompt_delta_preserves_order():
    added, _ = prompt_delta("a", "a, 三, 一, 二")
    assert added == ["三", "一", "二"]


def test_summarize_identical_returns_empty_string():
    assert summarize_delta("a, b", "a, b") == ""


def test_summarize_punctuation_only_change():
    assert summarize_delta("a,b", "a, b") == "无明显短语变化"


def test_summarize_contains_markers():
    text = summarize_delta("a, b", "a, c")
    assert text.startswith("+ c")
    assert "- b" in text


def test_summarize_removal_only():
    assert summarize_delta("a, b, c", "a") == "- b / c"
