#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${CODEX_HOME:-$HOME/.codex}/prompts"
BACKUP_ROOT="${CODEX_HOME:-$HOME/.codex}/backups/ai-berkshire-prompts/$(date +%Y%m%d-%H%M%S)"

python3 "$ROOT/scripts/sync-codex-prompts.py"
mkdir -p "$DEST"
for prompt in "$ROOT"/codex-prompts/*.md; do
  [ -f "$prompt" ] || continue
  name="$(basename "$prompt")"
  if [ -f "$DEST/$name" ] && ! cmp -s "$prompt" "$DEST/$name"; then
    mkdir -p "$BACKUP_ROOT"
    cp "$DEST/$name" "$BACKUP_ROOT/$name"
  fi
  cp "$prompt" "$DEST/$name"
done

echo "Installed Codex slash prompts to $DEST"
echo "Restart Codex to pick up new slash prompts."
