#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

SOURCE_DIR="${SOURCE_DIR:-/opt/ai-berkshire-source}"
RELEASE_ROOT="${RELEASE_ROOT:-/srv/ai-berkshire/releases}"
CURRENT_LINK="${CURRENT_LINK:-/srv/ai-berkshire/current}"
LEGACY_DIR="${LEGACY_DIR:-/opt/ai-berkshire}"
RUNTIME_DIR="${RUNTIME_DIR:-/var/lib/ai-berkshire}"
RUNTIME_SENTIMENT_STATUS="${RUNTIME_SENTIMENT_STATUS:-${RUNTIME_DIR}/sentiment-status.json}"
ORIGIN_URL="${ORIGIN_URL:-https://github.com/yuzi1441/ai-berkshire.git}"
SOURCE_BRANCH="${SOURCE_BRANCH:-main}"
PYTHON="${PYTHON:-/opt/ai-berkshire-venv/bin/python}"

mkdir -p "${RELEASE_ROOT}" "${RUNTIME_DIR}"
if [[ ! -d "${SOURCE_DIR}/.git" ]]; then
    git clone --depth 1 --branch "${SOURCE_BRANCH}" "${ORIGIN_URL}" "${SOURCE_DIR}"
else
    if [[ -n "$(git -C "${SOURCE_DIR}" status --porcelain --untracked-files=all)" ]]; then
        echo "source checkout is not clean: ${SOURCE_DIR}" >&2
        exit 1
    fi
    git -C "${SOURCE_DIR}" fetch --depth 1 origin "${SOURCE_BRANCH}"
    git -C "${SOURCE_DIR}" checkout --detach FETCH_HEAD
fi
git -C "${SOURCE_DIR}" diff --check

SOURCE_SHA="$(git -C "${SOURCE_DIR}" rev-parse HEAD)"
if [[ -f "${CURRENT_LINK}/.source-sha" ]] && [[ "$(<"${CURRENT_LINK}/.source-sha")" == "${SOURCE_SHA}" ]]; then
    echo "release ${SOURCE_SHA} is already current"
    exit 0
fi

STAMP="$(date +%Y%m%d-%H%M%S)"
FINAL_RELEASE="${RELEASE_ROOT}/${SOURCE_SHA:0:12}-${STAMP}"
STAGING_RELEASE="${FINAL_RELEASE}.next"
cleanup_staging() {
    local rc=$?
    if (( rc != 0 )) && [[ -n "${STAGING_RELEASE}" && -d "${STAGING_RELEASE}" ]]; then
        rm -rf -- "${STAGING_RELEASE}"
    fi
    exit "${rc}"
}
trap cleanup_staging EXIT
mkdir -p "${STAGING_RELEASE}"
rsync -a --exclude='.git' --exclude='.venv' "${SOURCE_DIR}/" "${STAGING_RELEASE}/"
ln -s "/opt/ai-berkshire-venv" "${STAGING_RELEASE}/.venv"
printf '%s\n' "${SOURCE_SHA}" > "${STAGING_RELEASE}/.source-sha"

PREVIOUS=""
if [[ -e "${CURRENT_LINK}" ]]; then
    PREVIOUS="$(readlink -f "${CURRENT_LINK}")"
elif [[ -d "${LEGACY_DIR}" ]]; then
    PREVIOUS="${LEGACY_DIR}"
fi

copy_runtime_file() {
    local relative="$1"
    if [[ -n "${PREVIOUS}" && -f "${PREVIOUS}/${relative}" ]]; then
        install -D -m 0644 "${PREVIOUS}/${relative}" "${STAGING_RELEASE}/${relative}"
    fi
}

for relative in \
    data/investment-dashboard/annual_report_dates.json \
    data/investment-dashboard/automation_status.json \
    data/investment-dashboard/intraday_technical.json \
    data/investment-dashboard/main_report_review.json \
    data/investment-dashboard/opportunity_scans.json \
    data/investment-dashboard/opportunity_scan_status.json \
    data/investment-dashboard/post_buy_alerts.json \
    data/investment-dashboard/post_buy_tracking.json \
    data/investment-dashboard/quotes/latest.json \
    data/sentiment/latest.json \
    site/data/annual_report_dates.json \
    site/data/automation_status.json \
    site/data/intraday_technical.json \
    site/data/main_report_review.json \
    site/data/opportunity_scans.json \
    site/data/opportunity_scan_status.json \
    site/data/post_buy_alerts.json \
    site/data/post_buy_tracking.json \
    site/data/quotes/latest.json \
    site/data/sentiment_status.json; do
    copy_runtime_file "${relative}"
done

# Keep runtime timestamps/results, but always apply the source-controlled
# schedule contract so retired jobs cannot remain stuck in the public status.
"${PYTHON}" "${STAGING_RELEASE}/tools/automation_status.py" \
    --path "${STAGING_RELEASE}/data/investment-dashboard/automation_status.json" normalize \
    --template "${SOURCE_DIR}/data/investment-dashboard/automation_status.json"

if [[ -n "${PREVIOUS}" && -d "${PREVIOUS}/reports" ]]; then
    rsync -a \
        --include='*/' \
        --include='*-technical-analysis-*.md' \
        --exclude='*' \
        "${PREVIOUS}/reports/" "${STAGING_RELEASE}/reports/"
fi
if [[ -f "${RUNTIME_DIR}/sentiment-last-success.json" ]]; then
    install -D -m 0644 "${RUNTIME_DIR}/sentiment-last-success.json" \
        "${STAGING_RELEASE}/data/sentiment/latest.json"
    install -D -m 0644 "${RUNTIME_DIR}/sentiment-last-success.json" \
        "${STAGING_RELEASE}/site/data/sentiment.json"
fi
if [[ -f "${RUNTIME_SENTIMENT_STATUS}" ]]; then
    install -D -m 0644 "${RUNTIME_SENTIMENT_STATUS}" \
        "${STAGING_RELEASE}/site/data/sentiment_status.json"
fi

"${PYTHON}" "${STAGING_RELEASE}/tools/migrate_manual_execution_reviews.py" \
    --repo-root "${STAGING_RELEASE}"
"${PYTHON}" "${STAGING_RELEASE}/tools/build_investment_dashboard.py" \
    --repo-root "${STAGING_RELEASE}"
"${PYTHON}" -m compileall -q "${STAGING_RELEASE}/tools"
(
    cd "${STAGING_RELEASE}"
    "${PYTHON}" -m unittest -q \
        tests.test_dashboard_action_classifier \
        tests.test_investment_dashboard \
        tests.test_market_snapshot
)

mv "${STAGING_RELEASE}" "${FINAL_RELEASE}"
OLD_RELEASE=""
if [[ -e "${CURRENT_LINK}" ]]; then
    OLD_RELEASE="$(readlink -f "${CURRENT_LINK}")"
fi
TEMP_LINK="/srv/ai-berkshire/.current-${SOURCE_SHA:0:12}-$$"
ln -s "${FINAL_RELEASE}" "${TEMP_LINK}"
mv -Tf "${TEMP_LINK}" "${CURRENT_LINK}"

if ! /usr/local/sbin/ai-berkshire-refresh-services; then
    if [[ -n "${OLD_RELEASE}" ]]; then
        ROLLBACK_LINK="/srv/ai-berkshire/.rollback-${SOURCE_SHA:0:12}-$$"
        ln -s "${OLD_RELEASE}" "${ROLLBACK_LINK}"
        mv -Tf "${ROLLBACK_LINK}" "${CURRENT_LINK}"
        /usr/local/sbin/ai-berkshire-refresh-services || true
    fi
    echo "release activation failed; current was restored" >&2
    exit 1
fi

CURRENT_RELEASE="$(readlink -f "${CURRENT_LINK}")"
RELEASE_ROOT_REAL="$(readlink -f "${RELEASE_ROOT}")"
for candidate in "${RELEASE_ROOT}"/*; do
    [[ -d "${candidate}" ]] || continue
    CANDIDATE_REAL="$(readlink -f "${candidate}")"
    [[ "$(dirname "${CANDIDATE_REAL}")" == "${RELEASE_ROOT_REAL}" ]] || continue
    if [[ "${CANDIDATE_REAL}" == "${CURRENT_RELEASE}" || "${CANDIDATE_REAL}" == "${OLD_RELEASE}" ]]; then
        continue
    fi
    rm -rf -- "${CANDIDATE_REAL}"
done

echo "published ${SOURCE_SHA} to ${FINAL_RELEASE}"
