#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

if [[ "${EUID}" -ne 0 ]]; then
    echo "run as root" >&2
    exit 2
fi

PASSWORD="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(24))
PY
)"
PASSWORD_HASH="$(caddy hash-password --plaintext "${PASSWORD}")"
TEMP_FILE="$(mktemp /etc/ai-berkshire/dashboard-caddy.env.XXXXXX)"
{
    printf 'DASHBOARD_ADMIN_USER=admin\n'
    printf 'DASHBOARD_ADMIN_PASSWORD_HASH=%s\n' "${PASSWORD_HASH}"
} > "${TEMP_FILE}"
chown root:caddy "${TEMP_FILE}"
chmod 0640 "${TEMP_FILE}"
mv -f "${TEMP_FILE}" /etc/ai-berkshire/dashboard-caddy.env
systemctl restart caddy.service
curl --fail --silent --show-error --user "admin:${PASSWORD}" \
    https://vps.06070419.xyz:8443/ >/dev/null
printf 'admin password (shown once): %s\n' "${PASSWORD}"
