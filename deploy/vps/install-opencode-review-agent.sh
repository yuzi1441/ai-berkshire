#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

OPENCODE_VERSION="1.18.25"
OPENCODE_LINUX_X64_SHA256="58a3729a6f3432dd6d2917fcc4a949788891a035818646ad480e12c947f56e78"
OPENCODE_LINUX_ARM64_SHA256="35ef77897425e41b5183a2c21ac4fb1d4d944d82a94e3c920f57b5490af11ac5"
REPO_ROOT="${REPO_ROOT:-/srv/ai-berkshire/current}"
CONFIG_ROOT="/etc/ai-berkshire/opencode"
SWAP_PATH="/swapfile-ai-berkshire"

if [[ "${EUID}" -ne 0 ]]; then
    echo "install-opencode-review-agent.sh must run as root" >&2
    exit 1
fi

# OpenCode's first boot can briefly exceed the free memory on the 1 GiB VPS.
# Add a dedicated, persistent safety net only when the host has no swap.
memory_kib="$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)"
swap_kib="$(awk '/^SwapTotal:/ {print $2}' /proc/meminfo)"
if (( memory_kib < 1572864 && swap_kib == 0 )); then
    if [[ ! -f "${SWAP_PATH}" ]]; then
        fallocate -l 1G "${SWAP_PATH}"
        chmod 0600 "${SWAP_PATH}"
        mkswap "${SWAP_PATH}" >/dev/null
    fi
    swapon "${SWAP_PATH}"
    if ! grep -qF "${SWAP_PATH} none swap sw 0 0" /etc/fstab; then
        printf '%s\n' "${SWAP_PATH} none swap sw 0 0" >> /etc/fstab
    fi
fi

case "$(uname -m)" in
    x86_64)
        archive_arch="x64"
        expected_sha256="${OPENCODE_LINUX_X64_SHA256}"
        ;;
    aarch64|arm64)
        archive_arch="arm64"
        expected_sha256="${OPENCODE_LINUX_ARM64_SHA256}"
        ;;
    *)
        echo "unsupported architecture: $(uname -m)" >&2
        exit 1
        ;;
esac

installed_version=""
if [[ -x /usr/local/bin/opencode ]]; then
    installed_version="$(/usr/local/bin/opencode --version 2>/dev/null | tr -d '[:space:]' || true)"
fi

if [[ "${installed_version}" != "${OPENCODE_VERSION}" ]]; then
    temp_dir="$(mktemp -d /var/tmp/ai-berkshire-opencode.XXXXXX)"
    trap 'find "${temp_dir}" -depth -delete 2>/dev/null || true' EXIT
    archive="${temp_dir}/opencode.tar.gz"
    url="https://github.com/anomalyco/opencode/releases/download/v${OPENCODE_VERSION}/opencode-linux-${archive_arch}.tar.gz"

    curl --fail --location --silent --show-error "${url}" --output "${archive}"
    printf '%s  %s\n' "${expected_sha256}" "${archive}" | sha256sum --check --status
    tar -xzf "${archive}" -C "${temp_dir}"
    binary="$(find "${temp_dir}" -type f -name opencode -print -quit)"
    if [[ -z "${binary}" ]]; then
        echo "opencode binary missing from release archive" >&2
        exit 1
    fi
    install -m 0755 "${binary}" /usr/local/bin/opencode
fi

install -d -m 0755 "${CONFIG_ROOT}/agent"
install -m 0644 "${REPO_ROOT}/deploy/opencode/opencode.json" "${CONFIG_ROOT}/opencode.json"
install -m 0644 \
    "${REPO_ROOT}/deploy/opencode/agent/fundamental-review-daily.md" \
    "${CONFIG_ROOT}/agent/fundamental-review-daily.md"
# Older experiments placed an external plugin package here. The production
# runner uses --pure and the explicit provider config, so keep this directory
# free of unreviewed external plugins.
find "${CONFIG_ROOT}" -maxdepth 1 -type f \
    \( -name package.json -o -name package-lock.json -o -name bun.lock \) -delete

actual_version="$(/usr/local/bin/opencode --version | tr -d '[:space:]')"
if [[ "${actual_version}" != "${OPENCODE_VERSION}" ]]; then
    echo "unexpected opencode version: ${actual_version}" >&2
    exit 1
fi

echo "OpenCode ${actual_version} installed with read-only fundamental review agent"
