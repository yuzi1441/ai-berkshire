#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

ENV_FILE="${AI_BERKSHIRE_ENV_FILE:-/etc/ai-berkshire/sentiment.env}"
REPO_ROOT="${REPO_ROOT:-/srv/ai-berkshire/current}"
TIMEOUT_SECONDS="${OPENCODE_REVIEW_TIMEOUT_SECONDS:-300}"

if [[ ! -x /usr/local/bin/opencode ]]; then
    echo "OpenCode CLI is not installed" >&2
    exit 1
fi
if [[ ! -r "${ENV_FILE}" ]]; then
    echo "missing model environment file: ${ENV_FILE}" >&2
    exit 1
fi
if [[ "$#" -eq 0 ]]; then
    echo "usage: ai-berkshire-opencode-review <review prompt>" >&2
    exit 2
fi

set -a
# This root-owned file is also used by the existing dashboard services.
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

if [[ -z "${OPENCODE_GO_API_KEY:-}" ]]; then
    echo "OPENCODE_GO_API_KEY is not configured" >&2
    exit 1
fi

export OPENCODE_CONFIG_DIR="/etc/ai-berkshire/opencode"
export OPENCODE_ENABLE_EXA="1"
export OPENCODE_DISABLE_AUTOUPDATE="1"

exec timeout --signal=TERM --kill-after=10 "${TIMEOUT_SECONDS}" \
    /usr/local/bin/opencode run \
    --pure \
    --agent fundamental-review-daily \
    --model opencode-go/deepseek-v4-flash \
    --format json \
    --dir "${REPO_ROOT}" \
    "$*"
