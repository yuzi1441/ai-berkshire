#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

REPO_ROOT="${REPO_ROOT:-/srv/ai-berkshire/current}"
PYTHON="${PYTHON:-${REPO_ROOT}/.venv/bin/python}"
RUNTIME_DIR="${RUNTIME_DIR:-/var/lib/ai-berkshire}"
INVESTMENT_DISPOSITIONS_PATH="${INVESTMENT_DISPOSITIONS_PATH:-${RUNTIME_DIR}/manual_investment_dispositions.json}"
LOCK_PATH="${LOCK_PATH:-/run/lock/ai-berkshire-runtime.lock}"
LOCK_RETRY_EXIT=75
LOCK_RETRY_COUNTER="${LOCK_RETRY_COUNTER:-/run/ai-berkshire-${1:-unknown}-lock-retries}"
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
CURRENT_PHASE="queued"
RUN_ID="${JOB}-$(date +%Y%m%dT%H%M%S)-$$"
SOURCE_SHA=""
if [[ -f "${REPO_ROOT}/.source-sha" ]]; then
    SOURCE_SHA="$(tr -d '[:space:]' < "${REPO_ROOT}/.source-sha")" || SOURCE_SHA=""
fi

if [[ ! -x "${PYTHON}" ]]; then
    PYTHON=/usr/bin/python3
fi

status_start() {
    STATUS_STARTED=1
    "${PYTHON}" "${REPO_ROOT}/tools/automation_status.py" start \
        --job-id "${JOB}" \
        --scheduled-for "$(date --iso-8601=seconds)" \
        --run-id "${RUN_ID}" \
        --phase "${CURRENT_PHASE}" \
        --source-sha "${SOURCE_SHA}" \
        --message "A股统一调度器正在执行"
}

status_phase() {
    CURRENT_PHASE="$1"
    local message="${2:-${CURRENT_PHASE}}"
    "${PYTHON}" "${REPO_ROOT}/tools/automation_status.py" phase \
        --job-id "${JOB}" \
        --run-id "${RUN_ID}" \
        --phase "${CURRENT_PHASE}" \
        --source-sha "${SOURCE_SHA}" \
        --message "${message}" || true
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
        --run-id "${RUN_ID}" \
        --phase "${CURRENT_PHASE}" \
        --source-sha "${SOURCE_SHA}" \
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

schedule_lock_retry() {
    local retry_count=0
    if [[ -f "${LOCK_RETRY_COUNTER}" ]]; then
        read -r retry_count < "${LOCK_RETRY_COUNTER}" || retry_count=0
    fi
    retry_count=$(( retry_count + 1 ))
    printf '%s\n' "${retry_count}" > "${LOCK_RETRY_COUNTER}"
    if (( retry_count >= 3 )); then
        echo "运行锁重试已达到上限（${retry_count}），不再安排新的 systemd 重试" >&2
        return 1
    fi
    if systemd-run \
        --unit="ai-berkshire-${JOB}-lock-retry-${retry_count}-$(date +%s)" \
        --on-active=5min \
        /bin/systemctl start "ai-berkshire-a-share-scheduler@${JOB}.service" >/dev/null; then
        echo "已安排 ${retry_count}/2 次运行锁延后重试" >&2
        return 0
    fi
    echo "无法安排运行锁延后重试" >&2
    return 1
}

clear_lock_retry_state() {
    unlink "${LOCK_RETRY_COUNTER}" 2>/dev/null || true
}

trap 'handle_signal SIGTERM' TERM
trap 'handle_signal SIGINT' INT
trap handle_exit EXIT

mkdir -p "$(dirname "${LOCK_PATH}")"
exec 9>"${LOCK_PATH}"
case "${JOB}" in
    market|intraday|deploy) LOCK_WAIT_SECONDS="${LOCK_WAIT_SECONDS:-180}" ;;
    *) LOCK_WAIT_SECONDS="${LOCK_WAIT_SECONDS:-900}" ;;
esac
if ! flock -w "${LOCK_WAIT_SECONDS}" 9; then
    if [[ -f "${REPO_ROOT}/tools/automation_status.py" ]]; then
        status_start
        CURRENT_PHASE="lock_wait"
    fi
    if schedule_lock_retry; then
        status_finish deferred "等待运行锁 ${LOCK_WAIT_SECONDS} 秒后延后；已安排 systemd 在 5 分钟后重试"
    else
        status_finish deferred "等待运行锁 ${LOCK_WAIT_SECONDS} 秒后延后；未安排新的 systemd 重试"
    fi
    exit "${LOCK_RETRY_EXIT}"
fi

if [[ "${JOB}" == "deploy" ]]; then
    status_start
    if /usr/local/sbin/ai-berkshire-publish-release; then
        status_finish ok "main 已构建、验证并原子切换 release"
        clear_lock_retry_state
        exit 0
    fi
    status_finish error "main 发布失败，current 保持上一 release"
    clear_lock_retry_state
    exit 1
fi

cd "${REPO_ROOT}"
status_start

build_dashboard() {
    "${PYTHON}" tools/build_investment_dashboard.py --repo-root "${REPO_ROOT}" \
        --investment-dispositions "${INVESTMENT_DISPOSITIONS_PATH}"
}

post_buy_check() {
    "${PYTHON}" tools/post_buy_tracking.py check
}

publish_sentiment_runtime() {
    if [[ -f "${RUNTIME_DIR}/sentiment-last-success.json" ]]; then
        install -D -m 0644 "${RUNTIME_DIR}/sentiment-last-success.json" \
            "${REPO_ROOT}/data/sentiment/latest.json"
        install -D -m 0644 "${RUNTIME_DIR}/sentiment-last-success.json" \
            "${REPO_ROOT}/site/data/sentiment.json"
    fi
    if [[ -f "${RUNTIME_DIR}/sentiment-status.json" ]]; then
        install -D -m 0644 "${RUNTIME_DIR}/sentiment-status.json" \
            "${REPO_ROOT}/site/data/sentiment_status.json"
    fi
}

run_annual() {
    status_phase build "重建看板"
    build_dashboard
    status_phase report_dates "更新报告日期"
    "${PYTHON}" tools/annual_report_dates.py --repo-root "${REPO_ROOT}" --as-of "${AS_OF}"
}

run_morning() {
    status_phase build "重建看板"
    build_dashboard
    status_phase post_buy_check "检查持仓跟踪"
    post_buy_check
    status_phase build "刷新持仓后的看板"
    build_dashboard
}

run_market() {
    status_phase market_snapshot "刷新 A/H 行情"
    "${PYTHON}" tools/market_snapshot.py --repo-root "${REPO_ROOT}" --markets A股,港股
    status_phase build "按同一行情快照重建状态"
    "${PYTHON}" tools/build_investment_dashboard.py --repo-root "${REPO_ROOT}" --state-only \
        --investment-dispositions "${INVESTMENT_DISPOSITIONS_PATH}"
}

run_intraday() {
    # 30m data is last-mile execution context; batch_intraday_technical.py
    # filters to PRE_BUY + intraday_eligible when the state layer is present.
    status_phase intraday "刷新 A 股盘中技术辅助"
    "${PYTHON}" tools/batch_intraday_technical.py \
        --repo-root "${REPO_ROOT}" \
        --markets A股 \
        --as-of "${AS_OF}" \
        --attempts 4 \
        --output "${REPO_ROOT}/data/investment-dashboard/intraday_technical.json"
    build_dashboard
}

run_close() {
    status_phase market_snapshot "刷新 A 股收盘行情"
    "${PYTHON}" tools/market_snapshot.py --repo-root "${REPO_ROOT}" --markets A股 --force
    status_phase post_buy_check "检查持仓跟踪"
    post_buy_check
    status_phase build "重建收盘看板"
    build_dashboard
}

run_daily() {
    # Daily technical output is the structured latest snapshot consumed by
    # Company State. Dated Markdown remains opt-in for research snapshots.
    status_phase technical "刷新 A/H 日线技术辅助"
    "${PYTHON}" tools/batch_technical_analysis.py \
        --repo-root "${REPO_ROOT}" \
        --markets A股 港股 \
        --as-of "${AS_OF}" \
        --attempts 4 \
        --force \
        --output "${REPO_ROOT}/data/investment-dashboard/technical_daily_snapshot.json" \
        --manifest "${REPO_ROOT}/logs/technical-analysis-batch-ah-${AS_OF//-/}.json"
    status_phase market_snapshot "刷新 A/H 收盘行情"
    "${PYTHON}" tools/market_snapshot.py --repo-root "${REPO_ROOT}" --markets A股,港股 --force
    status_phase post_buy_check "检查持仓跟踪"
    post_buy_check
    status_phase build "重建日常看板"
    build_dashboard
}

run_heavy() {
    # Data-plane only: collect deterministic A-share evidence and publish
    # compact packets for a local Codex/ChatGPT review.  Keeping --no-llm
    # explicit guarantees zero external model requests even while migration
    # secrets remain installed for rollback.
    local review_root="${RUNTIME_DIR}/local-review/${AS_OF}/input"
    local raw_sentiment="${RUNTIME_DIR}/local-review/${AS_OF}/raw-sentiment.json"
    status_phase sentiment_raw "抓取 A 股新闻与来源等级（不调用模型）"
    "${PYTHON}" tools/sentiment_snapshot.py \
        --board "${REPO_ROOT}/data/investment-dashboard/decision_board.json" \
        --registry "${REPO_ROOT}/data/report-routing/company_registry.json" \
        --output "${raw_sentiment}" \
        --working-output "${RUNTIME_DIR}/local-review/${AS_OF}/raw-working.json" \
        --cache-dir "${RUNTIME_DIR}/sentiment-cache" \
        --archive-dir "${RUNTIME_DIR}/local-review/${AS_OF}/raw-archive" \
        --site-output "${RUNTIME_DIR}/local-review/${AS_OF}/raw-site.json" \
        --status-output "${RUNTIME_DIR}/local-review/${AS_OF}/raw-status.json" \
        --lookback-days 7 \
        --fallback-lookback-days 30 \
        --news-limit 8 \
        --workers 3 \
        --markets A股 \
        --no-llm
    status_phase build "重建 deterministic 当前状态"
    build_dashboard
    status_phase local_review_prepare "生成本地每日复核 packets"
    rm -rf -- "${review_root}"
    "${PYTHON}" tools/local_daily_review.py prepare \
        --repo-root "${REPO_ROOT}" \
        --output-root "${review_root}" \
        --raw-sentiment "${raw_sentiment}" \
        --date "${AS_OF}"
    install -D -m 0644 "${review_root}/manifest.json" \
        "${REPO_ROOT}/data/investment-dashboard/daily_review_status.json"
    install -D -m 0644 "${review_root}/manifest.json" \
        "${REPO_ROOT}/site/data/daily_review_status.json"
    status_phase local_review_publish "同步 deterministic packets 到 generated branch"
    "${PYTHON}" scripts/publish_local_review_inputs.py --input-root "${review_root}"
    status_phase awaiting_local_review "等待本地 daily-investment-review"
    return 0
}

run_reconcile() {
    status_phase post_buy_check "检查持仓跟踪"
    post_buy_check
    status_phase build "重建对账看板"
    build_dashboard
}

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

if (( JOB_RC == 0 )); then
    if [[ "${JOB}" == "heavy" ]]; then
        status_finish ok "A 股 deterministic 数据已准备并同步；等待本地投资复核"
    else
        status_finish ok "任务完成；运行数据未提交到 Git"
    fi
    clear_lock_retry_state
    exit 0
fi
status_finish error "任务失败；线上保留上一份成功数据"
clear_lock_retry_state
exit 1
