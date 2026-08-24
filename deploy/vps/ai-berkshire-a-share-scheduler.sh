#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

REPO_ROOT="${REPO_ROOT:-/srv/ai-berkshire/current}"
PYTHON="${PYTHON:-${REPO_ROOT}/.venv/bin/python}"
LOCK_PATH="${LOCK_PATH:-/run/lock/ai-berkshire-runtime.lock}"
LOCK_RETRY_EXIT=75
LOCK_RETRY_COUNTER="/run/ai-berkshire-${1:-unknown}-lock-retries"
export TZ="Asia/Shanghai"

if [[ $# -ne 1 || ! "$1" =~ ^(deploy|annual|morning|market|intraday|close|daily|heavy|reconcile)$ ]]; then
    echo "usage: $0 deploy|annual|morning|market|intraday|close|daily|heavy|reconcile" >&2
    exit 2
fi

JOB="$1"
AS_OF="$(date +%F)"
STARTED_AT="$(date +%s)"
STATUS_STARTED=0
STATUS_FINISHED=0

if [[ ! -x "${PYTHON}" ]]; then
    PYTHON=/usr/bin/python3
fi

status_start() {
    STATUS_STARTED=1
    "${PYTHON}" "${REPO_ROOT}/tools/automation_status.py" start \
        --job-id "${JOB}" \
        --scheduled-for "$(date --iso-8601=seconds)" \
        --message "A股统一调度器正在执行"
}

status_finish() {
    local status="$1"
    local message="$2"
    local duration=$(( $(date +%s) - STARTED_AT ))
    "${PYTHON}" "${REPO_ROOT}/tools/automation_status.py" finish \
        --job-id "${JOB}" \
        --status "${status}" \
        --duration "${duration}" \
        --data-cutoff "${AS_OF}" \
        --message "${message}" || true
    STATUS_FINISHED=1
}

handle_signal() {
    local signal_name="$1"
    if (( STATUS_STARTED == 1 && STATUS_FINISHED == 0 )); then
        status_finish interrupted "任务收到 ${signal_name}；线上保留上一次成功结果"
    fi
    exit 130
}

handle_exit() {
    local rc=$?
    if (( rc != 0 && STATUS_STARTED == 1 && STATUS_FINISHED == 0 )); then
        status_finish error "任务异常退出（exit ${rc}）；请查看 journal"
    fi
}

trap 'handle_signal SIGTERM' TERM
trap 'handle_signal SIGINT' INT
trap handle_exit EXIT

mkdir -p /run/lock
exec 9>"${LOCK_PATH}"
case "${JOB}" in
    market|intraday|deploy) LOCK_WAIT_SECONDS="${LOCK_WAIT_SECONDS:-180}" ;;
    *) LOCK_WAIT_SECONDS="${LOCK_WAIT_SECONDS:-900}" ;;
esac
if ! flock -w "${LOCK_WAIT_SECONDS}" 9; then
    if [[ -f "${REPO_ROOT}/tools/automation_status.py" ]]; then
        status_start
        status_finish deferred "等待运行锁 ${LOCK_WAIT_SECONDS} 秒后延后；systemd 将在 5 分钟后重试"
    fi
    retry_count=0
    if [[ -f "${LOCK_RETRY_COUNTER}" ]]; then
        read -r retry_count < "${LOCK_RETRY_COUNTER}" || retry_count=0
    fi
    retry_count=$(( retry_count + 1 ))
    printf '%s\n' "${retry_count}" > "${LOCK_RETRY_COUNTER}"
    if (( retry_count < 3 )); then
        systemd-run \
            --unit="ai-berkshire-${JOB}-lock-retry-${retry_count}-$(date +%s)" \
            --on-active=5min \
            /bin/systemctl start "ai-berkshire-a-share-scheduler@${JOB}.service" >/dev/null
    fi
    exit "${LOCK_RETRY_EXIT}"
fi
if [[ -f "${LOCK_RETRY_COUNTER}" ]]; then
    unlink "${LOCK_RETRY_COUNTER}"
fi

if [[ "${JOB}" == "deploy" ]]; then
    status_start
    if /usr/local/sbin/ai-berkshire-publish-release; then
        status_finish ok "main 已构建、验证并原子切换 release"
        exit 0
    fi
    status_finish error "main 发布失败，current 保持上一 release"
    exit 1
fi

cd "${REPO_ROOT}"
status_start

build_dashboard() {
    "${PYTHON}" tools/build_investment_dashboard.py --repo-root "${REPO_ROOT}"
}

post_buy_check() {
    "${PYTHON}" tools/post_buy_tracking.py check
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
}

run_heavy() {
    # The close-after opportunity scan is intentionally separate from the
    # deterministic current-execution gate. It may populate the research
    # opportunity panel, but never changes a stock's executable status.
    local sentiment_rc=0
    local scan_rc=0
    "${PYTHON}" tools/sentiment_snapshot.py \
        --board "${REPO_ROOT}/data/investment-dashboard/decision_board.json" \
        --registry "${REPO_ROOT}/data/report-routing/company_registry.json" \
        --output "/var/lib/ai-berkshire/sentiment-last-success.json" \
        --working-output "/var/lib/ai-berkshire/sentiment-work-in-progress.json" \
        --cache-dir "/var/lib/ai-berkshire/sentiment-cache" \
        --archive-dir "/var/lib/ai-berkshire/sentiment-snapshots" \
        --site-output "${REPO_ROOT}/site/data/sentiment.json" \
        --status-output "${REPO_ROOT}/site/data/sentiment_status.json" \
        --lookback-days 7 \
        --fallback-lookback-days 30 \
        --news-limit 8 \
        --workers 3 \
        --markets A股 || sentiment_rc=$?
    "${PYTHON}" scripts/run_after_close_ai_review.py \
        --repo-root "${REPO_ROOT}" \
        --skip-git-sync \
        --markets A股 || scan_rc=$?
    build_dashboard
    if (( scan_rc != 0 )); then
        return "${scan_rc}"
    fi
    return 0
}

run_reconcile() {
    post_buy_check
    build_dashboard
}

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
JOB_RC=$?
set -e

if (( JOB_RC == 0 )); then
    status_finish ok "任务完成；运行数据未提交到 Git"
    exit 0
fi
status_finish error "任务失败；线上保留上一份成功数据，昂贵模型调用不自动重试"
exit 1
