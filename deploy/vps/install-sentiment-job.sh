#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

REPO_ROOT="${REPO_ROOT:-/opt/ai-berkshire}"

if [[ ! -x "${REPO_ROOT}/.venv/bin/python" ]]; then
    echo "missing VPS Python environment: ${REPO_ROOT}/.venv/bin/python" >&2
    exit 1
fi

install -D -m 0755 \
    "${REPO_ROOT}/deploy/vps/ai-berkshire-sentiment-update.sh" \
    /usr/local/sbin/ai-berkshire-sentiment-update
# Refresh the existing technical wrapper too so both jobs use the shared Git lock.
install -D -m 0755 \
    "${REPO_ROOT}/deploy/vps/ai-berkshire-technical-update.sh" \
    /usr/local/sbin/ai-berkshire-technical-update
install -D -m 0644 \
    "${REPO_ROOT}/deploy/vps/ai-berkshire-sentiment-update.service" \
    /etc/systemd/system/ai-berkshire-sentiment-update.service
install -D -m 0644 \
    "${REPO_ROOT}/deploy/vps/ai-berkshire-sentiment-update.timer" \
    /etc/systemd/system/ai-berkshire-sentiment-update.timer

install -d -m 0750 /etc/ai-berkshire
if [[ ! -f /etc/ai-berkshire/sentiment.env ]]; then
    install -m 0600 \
        "${REPO_ROOT}/deploy/vps/sentiment.env.example" \
        /etc/ai-berkshire/sentiment.env
fi

systemctl daemon-reload
systemctl enable --now ai-berkshire-sentiment-update.timer
systemctl list-timers ai-berkshire-sentiment-update.timer --no-pager
