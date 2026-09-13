#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${1:-$(pwd)}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
TRACKED_ROOT="${TRACKED_ROOT:-${REPO_ROOT}}"
TRACKED_ASSETS_MANIFEST="${TRACKED_ASSETS_MANIFEST:-}"

set -- --repo-root "${REPO_ROOT}" --require-canonical-reports
if [[ -n "${TRACKED_ASSETS_MANIFEST}" ]]; then
    set -- "$@" --tracked-assets-manifest "${TRACKED_ASSETS_MANIFEST}"
fi
if [[ -n "${INVESTMENT_DISPOSITIONS_PATH:-}" ]]; then
    set -- "$@" --investment-dispositions "${INVESTMENT_DISPOSITIONS_PATH}"
fi
"${PYTHON_BIN}" "${REPO_ROOT}/tools/build_investment_dashboard.py" "$@"
set -- --repo-root "${REPO_ROOT}" --require-tracked-assets --tracked-root "${TRACKED_ROOT}"
if [[ -n "${TRACKED_ASSETS_MANIFEST}" ]]; then
    set -- "$@" --tracked-assets-manifest "${TRACKED_ASSETS_MANIFEST}"
fi
"${PYTHON_BIN}" "${REPO_ROOT}/tools/validate_decision_state.py" "$@"
set -- --repo-root "${REPO_ROOT}" --require-canonical
if [[ -n "${TRACKED_ASSETS_MANIFEST}" ]]; then
    set -- "$@" --tracked-assets-manifest "${TRACKED_ASSETS_MANIFEST}"
fi
"${PYTHON_BIN}" "${REPO_ROOT}/tools/audit_current_reports.py" "$@"
"${PYTHON_BIN}" "${REPO_ROOT}/tools/audit_report_parsing.py" \
    --repo-root "${REPO_ROOT}"
