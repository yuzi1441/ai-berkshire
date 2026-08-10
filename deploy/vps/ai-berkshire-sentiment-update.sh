#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

REPO_ROOT="${REPO_ROOT:-/opt/ai-berkshire}"
PYTHON="${REPO_ROOT}/.venv/bin/python"
LOCK_PATH="/run/lock/ai-berkshire-repo-update.lock"

export TZ="Asia/Shanghai"

mkdir -p "${REPO_ROOT}/logs/vps"
exec 9>"${LOCK_PATH}"
if ! flock -n 9; then
    echo "another repository update is already running; exiting"
    exit 0
fi

cd "${REPO_ROOT}"
git pull --ff-only origin main

"${PYTHON}" tools/sentiment_snapshot.py \
    --lookback-days 7 \
    --news-limit 8 \
    --workers 3

git add -- data/sentiment

if git diff --cached --quiet; then
    echo "No sentiment changes to commit."
    exit 0
fi

git commit -m "chore: refresh A/H sentiment $(date +%F)"
git push origin main
