import csv
import os

from prompt_ledger.cli import main
from prompt_ledger.storage import Store


def run(root, *argv):
    return main(list(argv) + ["--root", str(root)])


def test_new_creates_shot(tmp_path, capsys):
    assert run(tmp_path, "new", "S1", "--project", "漫剧A") == 0
    assert "已创建镜头 S1" in capsys.readouterr().out
    assert "S1" in Store(root=str(tmp_path)).load().shots


def test_log_auto_creates_missing_shot(tmp_path, capsys):
    assert run(tmp_path, "log", "S9", "-p", "雨夜") == 0
    assert "已新建" in capsys.readouterr().out
    shot = Store(root=str(tmp_path)).load().shots["S9"]
    assert shot.attempts[0].prompt == "雨夜"


def test_log_with_accept(tmp_path):
    run(tmp_path, "log", "S1", "-p", "雨夜", "--accept")
    shot = Store(root=str(tmp_path)).load().shots["S1"]
    assert shot.attempts[0].outcome == "accepted"


def test_from_last_inherits_and_diffs(tmp_path, capsys):
    run(tmp_path, "log", "S1", "-p", "雨夜, 精致妆容", "-m", "seedance", "--reject", "expression")
    capsys.readouterr()
    run(tmp_path, "log", "S1", "--from-last", "-p", "雨夜, 眼妆花掉", "--accept")

    shot = Store(root=str(tmp_path)).load().shots["S1"]
    second = shot.attempts[1]
    assert second.model == "seedance"          # 继承自上一次
    assert second.based_on == 1
    assert "+ 眼妆花掉" in second.change
    assert "- 精致妆容" in second.change


def test_from_last_without_history_errors(tmp_path, capsys):
    assert run(tmp_path, "log", "S1", "--from-last") == 1
    assert "--from-last" in capsys.readouterr().err


def test_missing_prompt_errors(tmp_path, capsys):
    assert run(tmp_path, "log", "S1") == 1
    assert "缺少提示词" in capsys.readouterr().err


def test_invalid_reject_code_errors(tmp_path, capsys):
    assert run(tmp_path, "log", "S1", "-p", "a", "--reject", "nonsense") == 1
    assert "nonsense" in capsys.readouterr().err


def test_accept_marks_last_attempt(tmp_path):
    run(tmp_path, "log", "S1", "-p", "a", "--reject", "other")
    run(tmp_path, "accept", "S1")
    shot = Store(root=str(tmp_path)).load().shots["S1"]
    assert shot.attempts[-1].outcome == "accepted"
    assert shot.attempts[-1].reason == ""


def test_second_accept_requires_force(tmp_path, capsys):
    run(tmp_path, "log", "S1", "-p", "a", "--accept")
    run(tmp_path, "log", "S1", "-p", "b")
    assert run(tmp_path, "accept", "S1") == 1
    assert "--force" in capsys.readouterr().err


def test_force_accept_moves_the_mark(tmp_path):
    run(tmp_path, "log", "S1", "-p", "a", "--accept")
    run(tmp_path, "log", "S1", "-p", "b")
    assert run(tmp_path, "accept", "S1", "--force") == 0
    shot = Store(root=str(tmp_path)).load().shots["S1"]
    assert shot.attempts[0].outcome == "pending"
    assert shot.attempts[1].outcome == "accepted"


def test_reject_command(tmp_path):
    run(tmp_path, "log", "S1", "-p", "a")
    assert run(tmp_path, "reject", "S1", "--reason", "pacing") == 0
    shot = Store(root=str(tmp_path)).load().shots["S1"]
    assert shot.attempts[0].reason == "pacing"


def test_show_prints_attempts(tmp_path, capsys):
    run(tmp_path, "log", "S1", "-p", "雨夜", "--reject", "expression")
    capsys.readouterr()
    assert run(tmp_path, "show", "S1") == 0
    out = capsys.readouterr().out
    assert "#1" in out
    assert "情绪或表演不对" in out


def test_list_and_stats_run(tmp_path, capsys):
    run(tmp_path, "log", "S1", "-p", "a", "--accept")
    capsys.readouterr()
    assert run(tmp_path, "list") == 0
    assert "S1" in capsys.readouterr().out
    assert run(tmp_path, "stats") == 0
    assert "镜头总数" in capsys.readouterr().out


def test_export_csv_to_file(tmp_path, capsys):
    run(tmp_path, "log", "S1", "-p", "a, b", "--accept")
    out_path = tmp_path / "out.csv"
    assert run(tmp_path, "export", "-f", "csv", "-o", str(out_path)) == 0

    raw = out_path.read_text(encoding="utf-8-sig")
    rows = list(csv.DictReader(raw.splitlines()))
    assert len(rows) == 1
    assert rows[0]["shot_id"] == "S1"
    assert rows[0]["prompt"] == "a, b"


def test_export_json_prints_to_stdout(tmp_path, capsys):
    run(tmp_path, "log", "S1", "-p", "a")
    capsys.readouterr()
    assert run(tmp_path, "export", "-f", "json") == 0
    assert '"shot_id": "S1"' in capsys.readouterr().out


def test_unknown_shot_show_errors(tmp_path, capsys):
    assert run(tmp_path, "show", "nope") == 1
    assert "没有找到镜头" in capsys.readouterr().err


def test_root_flag_before_subcommand(tmp_path):
    assert main(["--root", str(tmp_path), "new", "S1"]) == 0
    assert os.path.exists(tmp_path / "ledger.json")
