#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

REPO_ROOT="${REPO_ROOT:-/opt/ai-berkshire}"
SOURCE_BRANCH="${SOURCE_BRANCH:-main}"
GENERATED_BRANCH="${GENERATED_BRANCH:-vps-generated}"

if [[ ! -x "${REPO_ROOT}/.venv/bin/python" ]]; then
    echo "missing VPS Python environment: ${REPO_ROOT}/.venv/bin/python" >&2
    exit 1
fi

cd "${REPO_ROOT}"
if [[ -n "$(git status --porcelain --untracked-files=all)" ]]; then
    echo "refusing to switch branches with pre-existing repository changes" >&2
    exit 1
fi
git fetch origin "${SOURCE_BRANCH}" "${GENERATED_BRANCH}" 2>/dev/null || git fetch origin "${SOURCE_BRANCH}"
if git show-ref --verify --quiet "refs/remotes/origin/${GENERATED_BRANCH}"; then
    if git show-ref --verify --quiet "refs/heads/${GENERATED_BRANCH}"; then
        git switch "${GENERATED_BRANCH}"
    else
        git switch --track -c "${GENERATED_BRANCH}" "origin/${GENERATED_BRANCH}"
    fi
else
    git switch -c "${GENERATED_BRANCH}" "origin/${SOURCE_BRANCH}"
    git push -u origin "${GENERATED_BRANCH}"
fi

install -D -m 0755 \
    "${REPO_ROOT}/deploy/vps/ai-berkshire-sentiment-update.sh" \
    /usr/local/sbin/ai-berkshire-sentiment-update
# Install the unified A-share scheduler. It is the only scheduled writer after
# this migration; the legacy A/H, US, sentiment, and independent opportunity
# timers are disabled below.
install -D -m 0755 \
    "${REPO_ROOT}/deploy/vps/ai-berkshire-a-share-scheduler.sh" \
    /usr/local/sbin/ai-berkshire-a-share-scheduler
install -D -m 0644 \
    "${REPO_ROOT}/deploy/vps/ai-berkshire-a-share-scheduler.service" \
    /etc/systemd/system/ai-berkshire-a-share-scheduler@.service

for timer in \
    annual morning market intraday close daily heavy reconcile; do
    install -D -m 0644 \
        "${REPO_ROOT}/deploy/vps/ai-berkshire-a-share-${timer}.timer" \
        "/etc/systemd/system/ai-berkshire-a-share-${timer}.timer"
done

install -d -m 0750 /etc/ai-berkshire
if [[ ! -f /etc/ai-berkshire/sentiment.env ]]; then
    install -m 0600 \
        "${REPO_ROOT}/deploy/vps/sentiment.env.example" \
        /etc/ai-berkshire/sentiment.env
fi

systemctl daemon-reload

# Remove the old independent writers before enabling the unified schedule.
systemctl disable --now \
    ai-berkshire-sentiment-update.timer \
    ai-berkshire-technical-update-ah.timer \
    ai-berkshire-technical-update-us.timer \
    ai-berkshire-after-close-review.timer 2>/dev/null || true

systemctl enable --now \
    ai-berkshire-a-share-annual.timer \
    ai-berkshire-a-share-morning.timer \
    ai-berkshire-a-share-market.timer \
    ai-berkshire-a-share-intraday.timer \
    ai-berkshire-a-share-close.timer \
    ai-berkshire-a-share-daily.timer \
    ai-berkshire-a-share-heavy.timer \
    ai-berkshire-a-share-reconcile.timer

systemctl list-timers 'ai-berkshire-a-share-*.timer' --no-pager
