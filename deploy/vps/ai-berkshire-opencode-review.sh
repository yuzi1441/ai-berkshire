#!/usr/bin/env bash
set -Eeuo pipefail

# An already-installed refresh script copies this transition-only tombstone
# during the first deployment across the provider migration.  It must never
# execute a legacy provider or silently fall back to another model authority.
echo "legacy model-runner command is retired; use the DeepSeek Official workflow" >&2
exit 64
