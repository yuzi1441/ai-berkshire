#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

ENV_FILE="${AI_BERKSHIRE_ENV_FILE:-/etc/ai-berkshire/sentiment.env}"
REPO_ROOT="${REPO_ROOT:-/srv/ai-berkshire/current}"
RUNTIME_DIR="${RUNTIME_DIR:-/var/lib/ai-berkshire/fundamental-review-layers}"
TIMEOUT_SECONDS="${OPENCODE_REVIEW_TIMEOUT_SECONDS:-600}"

usage() {
    cat <<'EOF'
usage:
  ai-berkshire-opencode-review seed
  ai-berkshire-opencode-review queue
  ai-berkshire-opencode-review daily (--ticker CODE | --all-due)
  ai-berkshire-opencode-review deep --model PROVIDER/MODEL [--variant high|max|xhigh] (--ticker CODE | --all-due)

Daily runs are manually started and always use DeepSeek Flash. Deep runs are
manually started and require a model selected from `opencode models`.
EOF
}

if [[ ! -x /usr/local/bin/opencode ]]; then
    echo "OpenCode CLI is not installed" >&2
    exit 1
fi
if [[ ! -r "${ENV_FILE}" ]]; then
    echo "missing model environment file: ${ENV_FILE}" >&2
    exit 1
fi
if [[ "$#" -lt 1 ]]; then
    usage >&2
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

command_name="$1"
shift
runner=("${REPO_ROOT}/.venv/bin/python" "${REPO_ROOT}/tools/run_fundamental_review.py"
    --repo-root "${REPO_ROOT}"
    --layers-dir "${RUNTIME_DIR}"
    --opencode-bin /usr/local/bin/opencode
    --timeout "${TIMEOUT_SECONDS}")

case "${command_name}" in
    seed)
        exec "${runner[@]}" --seed-legacy --publish
        ;;
    queue)
        exec "${runner[@]}" --seed-legacy --publish --queue
        ;;
    daily)
        exec "${runner[@]}" --layer daily --publish "$@"
        ;;
    deep)
        model=""
        previous=""
        for argument in "$@"; do
            if [[ "${previous}" == "--model" ]]; then
                model="${argument}"
                break
            fi
            previous="${argument}"
        done
        if [[ -z "${model}" ]]; then
            echo "deep review requires --model PROVIDER/MODEL" >&2
            exit 2
        fi
        if ! /usr/local/bin/opencode models | grep -Fxq "${model}"; then
            echo "model is not available from this VPS OpenCode configuration: ${model}" >&2
            exit 2
        fi
        exec "${runner[@]}" --layer deep --publish "$@"
        ;;
    *)
        usage >&2
        exit 2
        ;;
esac
