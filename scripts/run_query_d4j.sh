#!/usr/bin/env bash
set -euo pipefail

if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "OPENAI_API_KEY angeben!"
  exit 1
fi

JSON_DIR="/root/data/Defects4J/bug_report"
OUT_DIR="/root/libro/data/Defects4J/gen_tests"
LLM_SCRIPT="/root/libro/scripts/llm_query.py"

mkdir -p "$OUT_DIR"

count=1

for json in "$JSON_DIR"/*.json; do
  [ -e "$json" ] || continue
  fname=$(basename "$json" .json)
  project=${fname%%-*}
  bug_id=${fname##*-}

  for n in {0..49}; do
    python3.9 "$LLM_SCRIPT" -d d4j -p "$project" -b "$bug_id" --out "$OUT_DIR/${project}_${bug_id}_n${n}.txt"
    echo "$count: ${project}_${bug_id}_n${n}.txt"
    count=$((count + 1))
  done
done