#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

# Backward-compatibility bridge for releases whose already-installed refresh
# script still invokes this historical path.  The DeepSeek Official migration
# deliberately installs no external model runner.  Keep this script side-effect
# free so the old refresh can finish installing the new service stack; the new
# refresh script removes the retired command entry after a healthy restart.
echo "legacy model-runner installer bypassed; DeepSeek Official direct API is active"
