"""记录的持久化。

设计取舍：一个本地 JSON 文件，原子写入。

- 不用数据库：个人规模的数据（几千条）用 JSON 完全够，且可以直接用肉眼读、
  用 git 管、用别的脚本读。
- 原子写入：先写同目录临时文件再 os.replace，避免中途断电留下半个文件。
"""

from __future__ import annotations

import json
import os
import tempfile

from .model import Ledger, LedgerError

SCHEMA = 1
DEFAULT_DIR = ".prompt-ledger"


def resolve_root(root: str | None = None) -> str:
    """决定记录库所在目录。

    优先级：显式参数 > 环境变量 PROMPT_LEDGER_HOME > 用户主目录下的
    .prompt-ledger。
    """
    if root:
        return os.path.abspath(os.path.expanduser(root))
    env = os.environ.get("PROMPT_LEDGER_HOME")
    if env:
        return os.path.abspath(os.path.expanduser(env))
    return os.path.join(os.path.expanduser("~"), DEFAULT_DIR)


def _atomic_write(path: str, text: str) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".ledger-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class Store:
    def __init__(self, root: str | None = None):
        self.root = resolve_root(root)
        self.path = os.path.join(self.root, "ledger.json")

    def exists(self) -> bool:
        return os.path.exists(self.path)

    def load(self) -> Ledger:
        if not self.exists():
            return Ledger(schema=SCHEMA)
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except json.JSONDecodeError as exc:
            raise LedgerError(
                "记录库 {} 不是合法的 JSON（第 {} 行第 {} 列）。\n"
                "文件可能损坏，请先备份再手工修复。".format(
                    self.path, exc.lineno, exc.colno
                )
            ) from exc
        return Ledger.from_dict(data)

    def save(self, ledger: Ledger) -> None:
        text = json.dumps(ledger.to_dict(), ensure_ascii=False, indent=2)
        _atomic_write(self.path, text + "\n")
