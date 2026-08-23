#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

if [[ "${EUID}" -ne 0 ]]; then
    echo "run as root" >&2
    exit 2
fi

BOOTSTRAP_ROOT="${BOOTSTRAP_ROOT:-/opt/ai-berkshire}"
LEGACY_ROOT="/opt/ai-berkshire"
TEMP_PASSWORD="${DASHBOARD_TEMP_PASSWORD:-}"
if [[ -z "${TEMP_PASSWORD}" && ! -f /etc/ai-berkshire/dashboard-caddy.env ]]; then
    echo "DASHBOARD_TEMP_PASSWORD is required for first installation" >&2
    exit 2
fi

XRAY_BEFORE="$(ss -ltnp | awk '$4 ~ /:443$/ {print}')"
if [[ -z "${XRAY_BEFORE}" || "${XRAY_BEFORE}" != *xray* ]]; then
    echo "preflight failed: Xray is not the current TCP 443 listener" >&2
    exit 1
fi

LEGACY_DASHBOARD_WAS_ACTIVE=0
RESTORE_LEGACY_ON_ERROR=1
restore_legacy_on_error() {
    local exit_code=$?
    if [[ "${RESTORE_LEGACY_ON_ERROR}" -eq 1 && "${LEGACY_DASHBOARD_WAS_ACTIVE}" -eq 1 ]]; then
        systemctl stop caddy.service 2>/dev/null || true
        systemctl start ai-berkshire-dashboard.service 2>/dev/null || true
    fi
    exit "${exit_code}"
}
trap restore_legacy_on_error ERR

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl gnupg git rsync python3-venv
KEY_FILE="$(mktemp)"
SOURCE_FILE="$(mktemp)"
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' -o "${KEY_FILE}"
gpg --dearmor --yes -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg "${KEY_FILE}"
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' -o "${SOURCE_FILE}"
install -m 0644 "${SOURCE_FILE}" /etc/apt/sources.list.d/caddy-stable.list
chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg
apt-get update
if systemctl is-active --quiet ai-berkshire-dashboard.service; then
    LEGACY_DASHBOARD_WAS_ACTIVE=1
    systemctl stop ai-berkshire-dashboard.service
fi
apt-get install -y caddy

if ! id ai-berkshire >/dev/null 2>&1; then
    useradd --system --home /var/lib/ai-berkshire --shell /usr/sbin/nologin ai-berkshire
fi
install -d -m 0755 /srv/ai-berkshire/releases /opt/ai-berkshire-source
install -d -o ai-berkshire -g ai-berkshire -m 0750 /var/lib/ai-berkshire
install -d -o ai-berkshire -g ai-berkshire -m 0750 \
    /var/lib/ai-berkshire/sentiment-cache \
    /var/lib/ai-berkshire/sentiment-snapshots
install -d -m 0750 /etc/ai-berkshire

if [[ ! -f /var/lib/ai-berkshire/sentiment-last-success.json ]]; then
    LEGACY_SUCCESS_SNAPSHOT="$(python3 - "${LEGACY_ROOT}/data/sentiment" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
candidates = []
for path in [root / "latest.json", *(root / "snapshots").glob("*.json")]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        continue
    companies = payload.get("companies")
    if payload.get("status") != "ok" or not isinstance(companies, list) or not companies:
        continue
    candidates.append((str(payload.get("generated_at") or ""), str(path)))
if candidates:
    print(max(candidates)[1])
PY
)"
    if [[ -n "${LEGACY_SUCCESS_SNAPSHOT}" ]]; then
        install -o ai-berkshire -g ai-berkshire -m 0640 \
            "${LEGACY_SUCCESS_SNAPSHOT}" \
            /var/lib/ai-berkshire/sentiment-last-success.json
    fi
fi
if [[ -d "${LEGACY_ROOT}/data/sentiment/cache" ]]; then
    rsync -a --ignore-existing \
        "${LEGACY_ROOT}/data/sentiment/cache/" \
        /var/lib/ai-berkshire/sentiment-cache/
    chown -R ai-berkshire:ai-berkshire /var/lib/ai-berkshire/sentiment-cache
fi

if [[ ! -x /opt/ai-berkshire-venv/bin/python ]]; then
    python3 -m venv /opt/ai-berkshire-venv
    /opt/ai-berkshire-venv/bin/pip install --upgrade pip
    /opt/ai-berkshire-venv/bin/pip install -r "${BOOTSTRAP_ROOT}/requirements-technical.txt"
fi

if [[ ! -f /etc/ai-berkshire/dashboard-caddy.env ]]; then
    PASSWORD_HASH="$(caddy hash-password --plaintext "${TEMP_PASSWORD}")"
    {
        printf 'DASHBOARD_ADMIN_USER=admin\n'
        printf 'DASHBOARD_ADMIN_PASSWORD_HASH=%s\n' "${PASSWORD_HASH}"
    } > /etc/ai-berkshire/dashboard-caddy.env
fi
chown root:caddy /etc/ai-berkshire/dashboard-caddy.env
chmod 0640 /etc/ai-berkshire/dashboard-caddy.env

install -d -m 0755 /etc/systemd/system/caddy.service.d
install -D -m 0644 "${BOOTSTRAP_ROOT}/deploy/vps/caddy-systemd-override.conf" \
    /etc/systemd/system/caddy.service.d/ai-berkshire.conf

install -D -m 0755 "${BOOTSTRAP_ROOT}/deploy/vps/ai-berkshire-publish-release.sh" \
    /usr/local/sbin/ai-berkshire-publish-release
install -D -m 0755 "${BOOTSTRAP_ROOT}/deploy/vps/ai-berkshire-refresh-services.sh" \
    /usr/local/sbin/ai-berkshire-refresh-services

/usr/local/sbin/ai-berkshire-publish-release

systemctl disable --now \
    ai-berkshire-sentiment-update.timer \
    ai-berkshire-technical-update-ah.timer \
    ai-berkshire-technical-update-us.timer \
    ai-berkshire-after-close-review.timer 2>/dev/null || true
systemctl enable --now ai-berkshire-dashboard.service caddy.service
for timer in deploy annual morning market intraday close daily heavy reconcile; do
    systemctl enable --now "ai-berkshire-a-share-${timer}.timer"
done

XRAY_AFTER="$(ss -ltnp | awk '$4 ~ /:443$/ {print}')"
if [[ -z "${XRAY_AFTER}" || "${XRAY_AFTER}" != *xray* ]]; then
    echo "postflight failed: Xray no longer owns TCP 443" >&2
    exit 1
fi

curl --fail --silent --show-error http://127.0.0.1:8080/ >/dev/null
PUBLIC_STATUS=""
ADMIN_STATUS=""
ADMIN_AUTH_STATUS=""
for _attempt in $(seq 1 12); do
    PUBLIC_STATUS="$(curl --silent --output /dev/null --write-out '%{http_code}' \
        http://vps.06070419.xyz/ || true)"
    ADMIN_STATUS="$(curl --silent --output /dev/null --write-out '%{http_code}' \
        https://vps.06070419.xyz:8443/ || true)"
    if [[ -n "${TEMP_PASSWORD}" ]]; then
        ADMIN_AUTH_STATUS="$(curl --silent --output /dev/null --write-out '%{http_code}' \
            --user "admin:${TEMP_PASSWORD}" https://vps.06070419.xyz:8443/ || true)"
    else
        ADMIN_AUTH_STATUS="200"
    fi
    if [[ "${PUBLIC_STATUS}" == "200" && "${ADMIN_STATUS}" == "401" \
        && "${ADMIN_AUTH_STATUS}" == "200" ]]; then
        break
    fi
    sleep 5
done
[[ "${PUBLIC_STATUS}" == "200" ]]
PUBLIC_API_STATUS="$(curl --silent --output /dev/null --write-out '%{http_code}' http://vps.06070419.xyz/api/deep-reviews)"
[[ "${PUBLIC_API_STATUS}" == "404" ]]
[[ "${ADMIN_STATUS}" == "401" ]]
[[ "${ADMIN_AUTH_STATUS}" == "200" ]]

RESTORE_LEGACY_ON_ERROR=0
trap - ERR

echo "dashboard stack installed; legacy ${LEGACY_ROOT} was not modified or deleted"
