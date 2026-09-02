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
# The release/deploy job installs source code.  This runtime updater only
# refreshes local snapshots and must not mutate the checkout or Git history.

set +e
"${PYTHON}" tools/sentiment_snapshot.py \
    --lookback-days 7 \
    --fallback-lookback-days 30 \
    --news-limit 8 \
    --workers 3 \
    --markets A股 港股
SNAPSHOT_EXIT=$?
set -e

if (( SNAPSHOT_EXIT != 0 )); then
    # The Python job writes a checkpoint before exiting on interruption or
    # timeout. Keep every available partial artifact on the VPS only; runtime
    # jobs must not create a Git source of truth or push generated data.
    echo "partial sentiment snapshot retained in the local runtime directory"
    exit "${SNAPSHOT_EXIT}"
fi

echo "sentiment snapshot refreshed in the local runtime directory; no Git commit or push"
