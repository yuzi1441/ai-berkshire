#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

REPO_ROOT="${REPO_ROOT:-/opt/ai-berkshire}"
PYTHON="${REPO_ROOT}/.venv/bin/python"
LOCK_PATH="${LOCK_PATH:-/run/lock/ai-berkshire-repo-update.lock}"
export TZ="Asia/Shanghai"

if [[ $# -ne 1 || ! "$1" =~ ^(annual|morning|market|intraday|close|daily|heavy|reconcile)$ ]]; then
    echo "usage: $0 annual|morning|market|intraday|close|daily|heavy|reconcile" >&2
    exit 2
fi

JOB="$1"
AS_OF="$(date +%F)"
mkdir -p "${REPO_ROOT}/logs/vps"
exec 9>"${LOCK_PATH}"
LOCK_WAIT_SECONDS="${LOCK_WAIT_SECONDS:-180}"
if ! flock -w "${LOCK_WAIT_SECONDS}" 9; then
    echo "another repository update is still running; ${JOB} will be retried at its next scheduled time"
    exit 0
fi

cd "${REPO_ROOT}"

status_start() {
    local job_id="$1"
    "${PYTHON}" tools/automation_status.py start \
        --job-id "${job_id}" \
        --scheduled-for "$(date --iso-8601=seconds)" \
        --message "A股统一调度器正在执行"
}

status_finish() {
    local job_id="$1"
    local status="$2"
    local duration="$3"
    local message="$4"
    local record_count="${5:-}"
    local failed_count="${6:-}"
    "${PYTHON}" tools/automation_status.py finish \
        --job-id "${job_id}" \
        --status "${status}" \
        --duration "${duration}" \
        --data-cutoff "${AS_OF}" \
        ${record_count:+--record-count "${record_count}"} \
        ${failed_count:+--failed-count "${failed_count}"} \
        --message "${message}" || true
}

sync_repo() {
    if git diff --quiet && [[ -z "$(git status --porcelain --untracked-files=all)" ]]; then
        git pull --ff-only origin main
    else
        echo "pre-existing repository changes detected; skip pull to protect VPS outputs"
    fi
}

build_dashboard() {
    "${PYTHON}" tools/build_investment_dashboard.py
}

post_buy_check() {
    "${PYTHON}" tools/post_buy_tracking.py check
}

stock_count() {
    local path="$1"
    "${PYTHON}" - "${path}" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    print("", end="")
else:
    for key in ("record_count", "company_count", "quote_count", "generated_count", "scan_count"):
        if isinstance(payload.get(key), int):
            print(payload[key])
            break
PY
}

failed_count() {
    local path="$1"
    "${PYTHON}" - "${path}" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    print("", end="")
else:
    for key in ("failed_count", "error_count"):
        if isinstance(payload.get(key), int):
            print(payload[key])
            break
PY
}

stage_generated() {
    git add -- \
        data/investment-dashboard/annual_report_dates.json \
        data/investment-dashboard/automation_status.json \
        data/investment-dashboard/decision_board.json \
        data/investment-dashboard/decision_board_summary.json \
        data/investment-dashboard/decision_details \
        data/investment-dashboard/intraday_technical.json \
        data/investment-dashboard/opportunity_scans.json \
        data/investment-dashboard/post_buy_alerts.json \
        data/investment-dashboard/post_buy_tracking.json \
        data/investment-dashboard/quotes/latest.json \
        data/investment-dashboard/report_history.json \
        data/investment-dashboard/reports_catalog.json \
        data/sentiment \
        logs/technical-analysis-batch-*.json \
        reports/00-index/投资决策总表.md \
        reports/00-index/报告库-MOC.md \
        site/data/annual_report_dates.json \
        site/data/automation_status.json \
        site/data/decision_board.json \
        site/data/decision_board_summary.json \
        site/data/intraday_technical.json \
        site/data/opportunity_scans.json \
        site/data/post_buy_alerts.json \
        site/data/post_buy_tracking.json \
        site/data/quotes/latest.json \
        site/data/report_history.json \
        site/data/reports_catalog.json \
        site/data/sentiment.json \
        site/data/sentiment_status.json \
        site/data/decision_details \
        reports/*/*-technical-analysis-${AS_OF//-/}.md \
        2>/dev/null || true
}

commit_generated() {
    local message="$1"
    stage_generated
    if git diff --cached --quiet; then
        echo "No generated changes to commit."
        return 0
    fi
    git commit -m "${message} [skip ci]"
    git push origin main || echo "generated data is committed locally; push failed" >&2
}

run_annual() {
    build_dashboard
    "${PYTHON}" tools/annual_report_dates.py --repo-root "${REPO_ROOT}" --as-of "${AS_OF}"
}

run_morning() {
    build_dashboard
    post_buy_check
    build_dashboard
}

run_market() {
    "${PYTHON}" tools/market_snapshot.py --repo-root "${REPO_ROOT}" --markets A股
}

run_intraday() {
    "${PYTHON}" tools/batch_intraday_technical.py \
        --repo-root "${REPO_ROOT}" \
        --markets A股 \
        --as-of "${AS_OF}" \
        --attempts 4 \
        --output "${REPO_ROOT}/data/investment-dashboard/intraday_technical.json"
    build_dashboard
}

run_close() {
    "${PYTHON}" tools/market_snapshot.py --repo-root "${REPO_ROOT}" --markets A股 --force
    post_buy_check
    build_dashboard
    commit_generated "chore: close A-share dashboard ${AS_OF}"
}

run_daily() {
    "${PYTHON}" tools/batch_technical_analysis.py \
        --repo-root "${REPO_ROOT}" \
        --market A股 \
        --as-of "${AS_OF}" \
        --attempts 4 \
        --force \
        --manifest "${REPO_ROOT}/logs/technical-analysis-batch-a-share-${AS_OF//-/}.json"
    "${PYTHON}" tools/market_snapshot.py --repo-root "${REPO_ROOT}" --markets A股 --force
    post_buy_check
    build_dashboard
    commit_generated "chore: daily A-share dashboard ${AS_OF}"
}

run_heavy() {
    local sentiment_rc=0
    local opportunity_rc=0
    local started
    started="$(date +%s)"

    status_start sentiment
    set +e
    "${PYTHON}" tools/sentiment_snapshot.py \
        --repo-root "${REPO_ROOT}" \
        --lookback-days 7 \
        --fallback-lookback-days 30 \
        --news-limit 8 \
        --workers 3 \
        --markets A股
    sentiment_rc=$?
    set -e
    local sentiment_duration=$(( $(date +%s) - started ))
    if (( sentiment_rc == 0 )); then
        status_finish sentiment ok "${sentiment_duration}" "A股情绪更新完成" "$(stock_count data/sentiment/latest.json)" "$(failed_count site/data/sentiment_status.json)"
    else
        status_finish sentiment partial "${sentiment_duration}" "情绪更新部分失败，已保留阶段性结果" "$(stock_count data/sentiment/latest.json)" "$(failed_count site/data/sentiment_status.json)"
    fi

    status_start opportunity
    started="$(date +%s)"
    set +e
    "${PYTHON}" tools/opportunity_review.py scan \
        --repo-root "${REPO_ROOT}" \
        --output "${REPO_ROOT}/data/investment-dashboard/opportunity_scans.json"
    opportunity_rc=$?
    set -e
    local opportunity_duration=$(( $(date +%s) - started ))
    if (( opportunity_rc == 0 )); then
        status_finish opportunity ok "${opportunity_duration}" "A股机会扫描完成" "$(stock_count data/investment-dashboard/opportunity_scans.json)" "$(failed_count data/investment-dashboard/opportunity_scans.json)"
    else
        status_finish opportunity partial "${opportunity_duration}" "机会扫描部分失败，已保留扫描结果" "$(stock_count data/investment-dashboard/opportunity_scans.json)" "$(failed_count data/investment-dashboard/opportunity_scans.json)"
    fi

    build_dashboard
    commit_generated "chore: A-share sentiment and opportunity refresh ${AS_OF}"
    (( sentiment_rc == 0 && opportunity_rc == 0 ))
}

run_reconcile() {
    post_buy_check
    build_dashboard
    commit_generated "chore: reconcile A-share dashboard ${AS_OF}"
}

sync_repo
status_start "${JOB}"
started_at="$(date +%s)"
set +e
case "${JOB}" in
    annual) run_annual ;;
    morning) run_morning ;;
    market) run_market ;;
    intraday) run_intraday ;;
    close) run_close ;;
    daily) run_daily ;;
    heavy) run_heavy ;;
    reconcile) run_reconcile ;;
esac
job_rc=$?
set -e
duration=$(( $(date +%s) - started_at ))

job_status="ok"
if (( job_rc != 0 )); then
    job_status="partial"
fi
status_finish "${JOB}" "${job_status}" "${duration}" \
    "$([[ ${job_rc} -eq 0 ]] && echo '任务完成' || echo '任务部分失败，请查看日志')"
commit_generated "chore: finalize ${JOB} automation status ${AS_OF}"
exit "${job_rc}"
