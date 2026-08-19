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
# A previous interrupted run may have left generated snapshots or local VPS
# patches unstaged.  Do not overwrite those outputs with a pull; the job can
# still run against the current checkout and publish its own checkpoint.
if git diff --quiet && [[ -z "$(git status --porcelain --untracked-files=all)" ]]; then
    git pull --ff-only origin main
else
    echo "pre-existing repository changes detected; skip pull to protect VPS outputs"
fi

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
    # The Python job writes a checkpoint before exiting on interruption or
    # timeout. Publish every available partial artifact, not only the status,
    # so the dashboard can show the latest completed stages.
    for path in \
        data/sentiment/latest.json \
        site/data/sentiment.json \
        site/data/sentiment_status.json; do
        [[ -e "${path}" ]] && git add -- "${path}"
    done
    if ! git diff --cached --quiet; then
        git commit -m "chore: publish partial A-share sentiment $(date +%F-%H%M)"
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
