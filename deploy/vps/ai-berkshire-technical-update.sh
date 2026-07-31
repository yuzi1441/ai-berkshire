#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

REPO_ROOT="${REPO_ROOT:-/opt/ai-berkshire}"
PYTHON="${REPO_ROOT}/.venv/bin/python"
LOCK_PATH="/run/lock/ai-berkshire-technical-update.lock"

export TZ="Asia/Shanghai"

if [[ $# -ne 1 || ! "$1" =~ ^(ah|us|all)$ ]]; then
    echo "usage: $0 ah|us|all" >&2
    exit 2
fi

mkdir -p "${REPO_ROOT}/logs/vps"
exec 9>"${LOCK_PATH}"
if ! flock -n 9; then
    echo "another technical update is already running; exiting"
    exit 0
fi

cd "${REPO_ROOT}"
git pull --ff-only origin main

as_of="$(date +%F)"

run_market() {
    local market="$1"
    local label="$2"
    "${PYTHON}" tools/batch_technical_analysis.py \
        --market "${market}" \
        --as-of "${as_of}" \
        --attempts 4 \
        --force \
        --manifest "${REPO_ROOT}/logs/technical-analysis-batch-${label}-${as_of//-/}.json"
}

case "$1" in
    ah)
        run_market "A股" "a-share"
        run_market "港股" "hk"
        ;;
    us)
        run_market "美股" "us"
        ;;
    all)
        run_market "A股" "a-share"
        run_market "港股" "hk"
        run_market "美股" "us"
        ;;
esac

"${PYTHON}" tools/build_investment_dashboard.py
"${PYTHON}" tools/market_snapshot.py --force

git add -- \
    reports \
    data/investment-dashboard \
    site/data \
    logs/technical-analysis-batch-*.json

if git diff --cached --quiet; then
    echo "No generated changes to commit."
    exit 0
fi

git commit -m "chore: refresh technical analysis ${as_of}"
git push origin main
