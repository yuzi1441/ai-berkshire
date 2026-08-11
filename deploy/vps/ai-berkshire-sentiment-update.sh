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

set +e
"${PYTHON}" tools/sentiment_snapshot.py \
    --lookback-days 7 \
    --fallback-lookback-days 30 \
    --news-limit 8 \
    --workers 3 \
    --markets A股
SNAPSHOT_EXIT=$?
set -e

if (( SNAPSHOT_EXIT != 0 )); then
    # The Python job writes an error status without touching the last good
    # snapshot. Publish that status so the dashboard can show the failure.
    git add -- site/data/sentiment_status.json
    if ! git diff --cached --quiet; then
        git commit -m "chore: report A-share sentiment failure $(date +%F)"
        git push origin main
    fi
    exit "${SNAPSHOT_EXIT}"
fi

git add -- data/sentiment site/data/sentiment.json site/data/sentiment_status.json

if git diff --cached --quiet; then
    echo "No sentiment changes to commit."
    exit 0
fi

git commit -m "chore: refresh A-share sentiment $(date +%F)"
git push origin main
