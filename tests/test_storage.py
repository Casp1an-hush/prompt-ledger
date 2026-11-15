import json
import os

import pytest

from prompt_ledger.model import LedgerError
from prompt_ledger.storage import Store, resolve_root


def test_missing_ledger_returns_empty(tmp_path):
    store = Store(root=str(tmp_path))
    assert store.exists() is False
    assert store.load().shots == {}


def test_save_then_load(tmp_path):
    store = Store(root=str(tmp_path))
    ledger = store.load()
    ledger.add_shot("S1", project="P")
    store.save(ledger)

    assert store.exists()
    assert Store(root=str(tmp_path)).load().shots["S1"].project == "P"


def test_save_is_valid_utf8_json(tmp_path):
    store = Store(root=str(tmp_path))
    ledger = store.load()
    ledger.add_shot("镜头一", note="雨夜哭戏")
    store.save(ledger)

    raw = (tmp_path / "ledger.json").read_text(encoding="utf-8")
    assert "雨夜哭戏" in raw  # 中文没有被转义成 \uXXXX
    assert json.loads(raw)["schema"] == 1


def test_corrupt_file_raises_clear_error(tmp_path):
    (tmp_path / "ledger.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(LedgerError) as info:
        Store(root=str(tmp_path)).load()
    assert "不是合法的 JSON" in str(info.value)


def test_save_leaves_no_temp_files(tmp_path):
    store = Store(root=str(tmp_path))
    ledger = store.load()
    ledger.add_shot("S1")
    store.save(ledger)
    assert [p.name for p in tmp_path.iterdir()] == ["ledger.json"]


def test_save_creates_missing_directory(tmp_path):
    target = tmp_path / "deep" / "nested"
    store = Store(root=str(target))
    ledger = store.load()
    ledger.add_shot("S1")
    store.save(ledger)
    assert (target / "ledger.json").exists()


def test_resolve_root_prefers_explicit_argument(monkeypatch):
    monkeypatch.setenv("PROMPT_LEDGER_HOME", "/tmp/from-env")
    assert resolve_root("/tmp/explicit") == os.path.abspath("/tmp/explicit")


def test_resolve_root_uses_env(monkeypatch):
    monkeypatch.setenv("PROMPT_LEDGER_HOME", "/tmp/from-env")
    assert resolve_root() == os.path.abspath("/tmp/from-env")


def test_resolve_root_falls_back_to_home(monkeypatch):
    monkeypatch.delenv("PROMPT_LEDGER_HOME", raising=False)
    assert resolve_root().endswith(".prompt-ledger")
