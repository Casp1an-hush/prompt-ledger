import pytest

from prompt_ledger.model import Attempt, Ledger, LedgerError, Shot


def test_add_and_require_shot():
    ledger = Ledger()
    ledger.add_shot("S1", project="漫剧A", note="雨夜哭戏")
    assert ledger.require("S1").project == "漫剧A"


def test_duplicate_shot_rejected():
    ledger = Ledger()
    ledger.add_shot("S1")
    with pytest.raises(LedgerError):
        ledger.add_shot("S1")


def test_require_missing_shot():
    with pytest.raises(LedgerError):
        Ledger().require("nope")


def test_attempt_numbering():
    shot = Shot(id="S1")
    assert shot.next_n() == 1
    shot.attempts.append(Attempt(n=1))
    assert shot.next_n() == 2


def test_accepted_returns_first_accepted():
    shot = Shot(id="S1")
    shot.attempts = [
        Attempt(n=1, outcome="rejected", reason="expression"),
        Attempt(n=2, outcome="accepted"),
        Attempt(n=3, outcome="pending"),
    ]
    assert shot.accepted().n == 2


def test_accepted_is_none_when_nothing_accepted():
    shot = Shot(id="S1")
    shot.attempts = [Attempt(n=1, outcome="pending")]
    assert shot.accepted() is None


def test_round_trip_preserves_everything():
    ledger = Ledger()
    shot = ledger.add_shot("S1", project="P", note="n")
    shot.attempts.append(
        Attempt(
            n=1,
            prompt="a, b",
            negative="c",
            model="seedance",
            ratio="9:16",
            seed=42,
            refs=["refs/x.png"],
            outcome="rejected",
            reason="consistency",
            note="站位穿帮",
            based_on=0,
            change="+ a",
            ts="2026-11-16T10:00:00",
        )
    )

    restored = Ledger.from_dict(ledger.to_dict())
    attempt = restored.shots["S1"].attempts[0]
    assert attempt.prompt == "a, b"
    assert attempt.seed == 42
    assert attempt.refs == ["refs/x.png"]
    assert attempt.reason == "consistency"
    assert attempt.based_on == 0


def test_unknown_schema_rejected():
    with pytest.raises(LedgerError):
        Ledger.from_dict({"schema": 99, "shots": []})


def test_seed_none_round_trips():
    attempt = Attempt(n=1, seed=None)
    assert Attempt.from_dict(attempt.to_dict()).seed is None
