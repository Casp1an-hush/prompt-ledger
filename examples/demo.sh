#!/usr/bin/env bash
# Reproduce the example from the README.
# Uses a temporary ledger so your real ~/.prompt-ledger is untouched.
set -euo pipefail

export PROMPT_LEDGER_HOME="$(mktemp -d)"
PL="${PL:-prompt-ledger}"

$PL new S01-SC03-SH02 --project "漫剧A" --note "雨夜哭戏"

$PL log S01-SC03-SH02 \
  -p "雨夜, 特写, 女主哭泣, 精致妆容, 柔光, 唯美" \
  -m seedream -r 9:16 \
  --reject expression --note "她哭得太好看了"

$PL log S01-SC03-SH02 --from-last \
  -p "雨夜, 特写, 女主哭泣, 哭到第十秒, 眼妆花掉, 鼻头发红, 视线避开镜头, 下颌紧绷" \
  --accept

echo
$PL show S01-SC03-SH02
echo
$PL stats

rm -rf "$PROMPT_LEDGER_HOME"
