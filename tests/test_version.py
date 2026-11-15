"""版本号一致性测试。

版本在两个地方硬编码：`pyproject.toml` 的 `version` 和
`prompt_ledger.__init__.__version__`。v0.2.0 就曾因只改了 tag、忘了改这两处，
导致安装后 `--version` 还报旧版本。这个测试防止它们再次漂移。
"""

import pathlib
import re

from prompt_ledger import __version__

_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_version_matches_pyproject():
    text = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match, "pyproject.toml 缺少 [project] version 字段"
    assert __version__ == match.group(1), (
        "__version__ 是 {!r}，pyproject.toml 里是 {!r}，两者必须一致".format(
            __version__, match.group(1)
        )
    )


def test_version_is_plain_semver():
    # 项目刻意只用 x.y.z 三段纯数字；将来若要发预发布版（0.3.0rc1），
    # 这里应当换成真正的 PEP 440 校验，而不是继续放宽这个名字。
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__), __version__
