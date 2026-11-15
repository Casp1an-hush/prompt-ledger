# prompt-ledger

**Record what you actually change between generations — not just the final image.**

A small command-line tool for keeping an auditable record of prompt iterations in
AI-generated video and image work. Each generation is logged as one attempt under
one shot, so the path from first prompt to accepted output stays searchable,
comparable and exportable.

---

## Why

Prompt work is easy to lose. A shot that takes forty generations to get right
looks identical to one that took two, once the file is delivered. The iteration
itself — what was added, what was removed, why a take was rejected — usually
survives only in someone's memory.

That has two consequences:

- **For the person doing the work**, process knowledge evaporates. The lesson
  learned at generation #23 is not written down anywhere and has to be relearned
  on the next shot.
- **For anyone studying the work**, there is no record to study. A claim like
  "this took skill, not luck" cannot be checked against anything.

`prompt-ledger` is a deliberately small attempt at fixing the second problem. It
records each generation request as a unit with its prompt, negative prompt,
model, aspect ratio, seed, reference images, outcome and rejection reason — and
then computes the difference between consecutive versions.

## What it looks like

```
$ prompt-ledger show S01-SC03-SH02
S01-SC03-SH02  漫剧A  · 雨夜哭戏
========================================
  #1  2026-11-16T01:39:55  seedream  9:16
    结果  拒绝 · 情绪或表演不对
    提示  雨夜, 特写, 女主哭泣, 精致妆容, 柔光, 唯美
    备注  她哭得太好看了

  #2  2026-11-16T01:39:55  seedream  9:16
    结果  通过
    提示  雨夜, 特写, 女主哭泣, 哭到第十秒, 眼妆花掉, 鼻头发红, 视线避开镜头, 下颌紧绷
    变化  + 哭到第十秒 / 眼妆花掉 / 鼻头发红 / 视线避开镜头 / 下颌紧绷；- 精致妆容 / 柔光 / 唯美
```

And:

```
$ prompt-ledger stats
镜头总数      1
已通过        1
未通过        0
生成请求总数  2

平均第几次通过  2.00
中位第几次通过  2

拒绝原因分布
  expression      1  情绪或表演不对

按模型
  seedream             请求    2  被拒    1
```

## Install

Requires Python 3.9+.

Install straight from the repository — no clone needed:

```bash
pip install git+https://github.com/zjy053231-crypto/prompt-ledger.git
```

Or, to get the `prompt-ledger` command in an isolated environment:

```bash
pipx install git+https://github.com/zjy053231-crypto/prompt-ledger.git
```

To work on the code instead:

```bash
git clone https://github.com/zjy053231-crypto/prompt-ledger.git
cd prompt-ledger
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Quick start

```bash
# 1. create a shot
prompt-ledger new S01-SC03-SH02 --project "漫剧A" --note "雨夜哭戏"

# 2. log a rejected attempt
prompt-ledger log S01-SC03-SH02 \
  -p "雨夜, 特写, 女主哭泣, 精致妆容, 柔光, 唯美" \
  -m seedream -r 9:16 --reject expression --note "她哭得太好看了"

# 3. log the next attempt, inheriting unchanged parameters
prompt-ledger log S01-SC03-SH02 --from-last \
  -p "雨夜, 特写, 女主哭泣, 哭到第十秒, 眼妆花掉, 鼻头发红, 视线避开镜头, 下颌紧绷" \
  --accept
```

`--from-last` is the point of the tool's ergonomics: you only type what you
changed. Everything else — model, ratio, seed, negative prompt, reference
images — is inherited, and the change summary is computed automatically.

## How it works

Two levels:

| Level | Meaning |
|---|---|
| **shot** | A unit of content — one shot, one scene, one thumbnail set |
| **attempt** | One generation request: prompt, negative, model, ratio, seed, refs, outcome, reason |

An attempt can be derived from an earlier one (`--from-last`, `--base N`). When
it is, the stored `change` field records the phrase-level difference between the
two prompts.

### Rejection reasons are a fixed vocabulary

```
consistency   角色／场景前后不一致
expression    情绪或表演不对
composition   构图、机位或景别不对
artifact      画面崩坏、穿帮或畸形
style         画风偏移或风格不统一
text          文字、字幕或符号错误
pacing        节奏、时长或运镜不对
other         其他
```

Free-text rejection notes cannot be counted, and "why was this take rejected"
is the single most informative part of an iteration path. A closed set lets you
ask questions like *which class of problem does this team spend the most
generations on*.

### Prompts are diffed by phrase, not by character

Prompts are in practice comma-separated phrase lists. `"雨夜, 精致妆容, 柔光"` →
`"雨夜, 眼妆花掉, 鼻头发红"` is meaningfully a removal of two phrases and an
addition of two others; a character-level diff of the same change is unreadable.
So `diff.py` tokenises on `,` `，` `、` `;` `；` and newlines and compares phrase
sets, preserving order.

## Commands

| Command | Purpose |
|---|---|
| `new <shot>` | Create a shot |
| `log <shot>` | Record one generation request |
| `accept <shot> [--attempt N]` | Mark an attempt accepted |
| `reject <shot> --reason CODE` | Mark an attempt rejected |
| `list` | All shots, attempt counts, status |
| `show <shot>` | Full attempt history |
| `stats` | Aggregate metrics |
| `export [-f csv\|json] [-o PATH]` | Flattened rows for pandas / Excel |
| `reasons` | Print the rejection code table |

Common options on `log`: `-p/--prompt`, `-n/--negative`, `-m/--model`,
`-r/--ratio`, `-s/--seed`, `--ref PATH` (repeatable), `--from-last`, `--base N`,
`--note`, `--accept`, `--reject CODE`.

## Analysing the export

```bash
prompt-ledger export -f csv -o iterations.csv
```

```python
import pandas as pd

df = pd.read_csv("iterations.csv")
df.groupby("reason").size().sort_values(ascending=False)
df.groupby("shot_id")["attempt"].max().describe()
```

The CSV is written with a UTF-8 BOM when saved to a file, so Excel opens the
Chinese columns correctly on a double-click.

## Storage

One JSON file, default `~/.prompt-ledger/ledger.json`. Override with
`--root DIR` or the `PROMPT_LEDGER_HOME` environment variable.

Writes are atomic (temp file + `os.replace`), so an interrupted command cannot
leave a half-written ledger. A malformed file produces a clear error naming the
file and the line, rather than a traceback.

No database, no server, no network. The ledger is plain text and can be kept in
version control.

## Design notes and limits

- **It records; it does not judge.** The tool has no opinion on whether a take
  is good. That judgement stays with the person, which is rather the argument
  the tool exists to support.
- **Diff is phrase-level, not semantic.** Reordering phrases or swapping
  synonyms registers as a change. This is intentional — it keeps the record
  mechanical and auditable — but it means `change` is a log, not an analysis.
- **No image storage.** Reference images are recorded as paths, not copied. If
  the files move, the paths go stale.
- **Single-user, single-process.** No file locking. Do not run two writes
  against the same ledger at once.

## Prior art

The general idea — keeping prompts and generated assets together in one project
workspace — is present in [Reveric](https://github.com/looplj/reveric), an
AGPL-3.0 AI novel / short-drama desktop application whose storyboard module ties
prompts to assets. That project is a full production suite; this one is a
several-hundred-line record keeper. **No code is shared between the two**, and
the credit here is for the framing, not the implementation.

## License

MIT. See [LICENSE](LICENSE).
