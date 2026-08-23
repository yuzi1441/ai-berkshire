#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

REPO_ROOT="${REPO_ROOT:-/srv/ai-berkshire/current}"
ENV_FILE="/etc/ai-berkshire/dashboard-caddy.env"
BACKUP_DIR="$(mktemp -d /var/lib/ai-berkshire/service-backup.XXXXXX)"

backup_file() {
    local path="$1"
    if [[ -f "${path}" ]]; then
        install -D -m 0600 "${path}" "${BACKUP_DIR}${path}"
    fi
}

restore_file() {
    local path="$1"
    if [[ -f "${BACKUP_DIR}${path}" ]]; then
        install -D -m 0644 "${BACKUP_DIR}${path}" "${path}"
    fi
}

for path in \
    /etc/caddy/Caddyfile \
    /etc/systemd/system/ai-berkshire-dashboard.service \
    /etc/systemd/system/ai-berkshire-a-share-scheduler@.service \
    /usr/local/sbin/ai-berkshire-a-share-scheduler \
    /usr/local/sbin/ai-berkshire-publish-release \
    /usr/local/sbin/ai-berkshire-refresh-services; do
    backup_file "${path}"
done
for timer in deploy annual morning market intraday close daily heavy reconcile; do
    backup_file "/etc/systemd/system/ai-berkshire-a-share-${timer}.timer"
done

ADMIN_USER=""
ADMIN_HASH=""
while IFS='=' read -r key value; do
    case "${key}" in
        DASHBOARD_ADMIN_USER) ADMIN_USER="${value}" ;;
        DASHBOARD_ADMIN_PASSWORD_HASH) ADMIN_HASH="${value}" ;;
    esac
done < "${ENV_FILE}"
if [[ -z "${ADMIN_USER}" || -z "${ADMIN_HASH}" ]]; then
    echo "missing Caddy admin credentials in ${ENV_FILE}" >&2
    exit 1
fi

DASHBOARD_ADMIN_USER="${ADMIN_USER}" \
DASHBOARD_ADMIN_PASSWORD_HASH="${ADMIN_HASH}" \
    caddy validate --config "${REPO_ROOT}/deploy/vps/Caddyfile"

install -D -m 0755 "${REPO_ROOT}/deploy/vps/ai-berkshire-a-share-scheduler.sh" \
    /usr/local/sbin/ai-berkshire-a-share-scheduler
install -D -m 0755 "${REPO_ROOT}/deploy/vps/ai-berkshire-publish-release.sh" \
    /usr/local/sbin/ai-berkshire-publish-release
install -D -m 0755 "${REPO_ROOT}/deploy/vps/ai-berkshire-refresh-services.sh" \
    /usr/local/sbin/ai-berkshire-refresh-services
install -D -m 0644 "${REPO_ROOT}/deploy/systemd/ai-berkshire-dashboard.service" \
    /etc/systemd/system/ai-berkshire-dashboard.service
install -D -m 0644 "${REPO_ROOT}/deploy/vps/ai-berkshire-a-share-scheduler.service" \
    /etc/systemd/system/ai-berkshire-a-share-scheduler@.service
install -D -m 0644 "${REPO_ROOT}/deploy/vps/Caddyfile" /etc/caddy/Caddyfile
for timer in deploy annual morning market intraday close daily heavy reconcile; do
    install -D -m 0644 "${REPO_ROOT}/deploy/vps/ai-berkshire-a-share-${timer}.timer" \
        "/etc/systemd/system/ai-berkshire-a-share-${timer}.timer"
done

rollback() {
    echo "service refresh failed; restoring previous configuration" >&2
    restore_file /etc/caddy/Caddyfile
    restore_file /etc/systemd/system/ai-berkshire-dashboard.service
    restore_file /etc/systemd/system/ai-berkshire-a-share-scheduler@.service
    restore_file /usr/local/sbin/ai-berkshire-a-share-scheduler
    restore_file /usr/local/sbin/ai-berkshire-publish-release
    restore_file /usr/local/sbin/ai-berkshire-refresh-services
    for timer in deploy annual morning market intraday close daily heavy reconcile; do
        restore_file "/etc/systemd/system/ai-berkshire-a-share-${timer}.timer"
    done
    systemctl daemon-reload
    systemctl restart ai-berkshire-dashboard.service || true
    systemctl restart caddy.service || true
}
trap rollback ERR

systemctl daemon-reload
systemctl restart ai-berkshire-dashboard.service
systemctl restart caddy.service
for _attempt in 1 2 3 4 5 6; do
    if curl --fail --silent --show-error http://127.0.0.1:8080/ >/dev/null; then
        break
    fi
    sleep 1
done
curl --fail --silent --show-error http://127.0.0.1:8080/ >/dev/null
systemctl is-active --quiet ai-berkshire-dashboard.service
systemctl is-active --quiet caddy.service

trap - ERR
echo "dashboard services refreshed from ${REPO_ROOT}"
