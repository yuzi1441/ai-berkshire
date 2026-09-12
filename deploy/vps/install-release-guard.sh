#!/usr/bin/env bash
# Install only the release guard. No fetch, publish, service restart or model call.
# During the one-time migration, mask deploy and hold the runtime lock first;
# see README-dashboard-stack.md. Refresh invokes this while already holding it.
set -Eeuo pipefail
IFS=$'\n\t'

BOOTSTRAP_ROOT="${BOOTSTRAP_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
RELEASE_GUARD_PREFIX="${RELEASE_GUARD_PREFIX:-/usr/local}"
BOOTSTRAP_PYTHON="${BOOTSTRAP_PYTHON:-python3}"

# Validate every input before replacing the entry used by the existing scheduler.
bash -n "${BOOTSTRAP_ROOT}/deploy/vps/ai-berkshire-publish-release.sh"
bash -n "${BOOTSTRAP_ROOT}/deploy/vps/ai-berkshire-refresh-services.sh"
"${BOOTSTRAP_PYTHON}" - "${BOOTSTRAP_ROOT}" <<'PY'
import ast
import sys
from pathlib import Path

root = Path(sys.argv[1])
for name in ("verify_github_ci.py", "release_validation_record.py"):
    path = root / "tools" / name
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
PY

install -d -m 0755 "${RELEASE_GUARD_PREFIX}/lib/ai-berkshire-release-gate" "${RELEASE_GUARD_PREFIX}/sbin"
BUNDLE="$(mktemp -d "${RELEASE_GUARD_PREFIX}/lib/ai-berkshire-release-gate/bundle.XXXXXX")"
chmod 0755 "${BUNDLE}"
install -m 0755 "${BOOTSTRAP_ROOT}/deploy/vps/ai-berkshire-publish-release.sh" "${BUNDLE}/publisher.sh"
install -m 0755 "${BOOTSTRAP_ROOT}/deploy/vps/ai-berkshire-refresh-services.sh" "${BUNDLE}/refresh-services.sh"
install -m 0644 "${BOOTSTRAP_ROOT}/tools/verify_github_ci.py" "${BUNDLE}/verify_github_ci.py"
install -m 0644 "${BOOTSTRAP_ROOT}/tools/release_validation_record.py" "${BUNDLE}/release_validation_record.py"

ENTRY="${RELEASE_GUARD_PREFIX}/sbin/ai-berkshire-publish-release"
REFRESH_ENTRY="${RELEASE_GUARD_PREFIX}/sbin/ai-berkshire-refresh-services"
if [[ -e "${ENTRY}" ]]; then
    cp -p "${ENTRY}" "${BUNDLE}/previous-entry"
fi
if [[ -e "${REFRESH_ENTRY}" ]]; then
    cp -p "${REFRESH_ENTRY}" "${BUNDLE}/previous-refresh"
fi
TEMP_ENTRY="$(mktemp "${RELEASE_GUARD_PREFIX}/sbin/.release-guard.XXXXXX")"
{
    printf '#!/usr/bin/env bash\nset -Eeuo pipefail\n'
    printf 'export RELEASE_GATE_TOOLS=%q\n' "${BUNDLE}"
    printf 'export REQUIRE_GITHUB_CI=1\n'
    printf 'export REFRESH_SERVICES=%q\n' "${BUNDLE}/refresh-services.sh"
    printf 'exec /bin/bash %q "$@"\n' "${BUNDLE}/publisher.sh"
} > "${TEMP_ENTRY}"
bash -n "${TEMP_ENTRY}"
chmod 0755 "${TEMP_ENTRY}"
TEMP_REFRESH="$(mktemp "${RELEASE_GUARD_PREFIX}/sbin/.release-refresh.XXXXXX")"
install -m 0755 "${BUNDLE}/refresh-services.sh" "${TEMP_REFRESH}"
# os.replace replaces the entry itself even if it used to be a symlink.
"${BOOTSTRAP_PYTHON}" - "${TEMP_ENTRY}" "${ENTRY}" "${TEMP_REFRESH}" "${REFRESH_ENTRY}" <<'PY'
import os
import sys
os.replace(sys.argv[3], sys.argv[4])
os.replace(sys.argv[1], sys.argv[2])
PY
echo "release guard installed at ${ENTRY}; pinned bundle ${BUNDLE}; no release was published"
