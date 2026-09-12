#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${CODEX_HOME:-$HOME/.codex}/skills"
BACKUP_ROOT="${CODEX_HOME:-$HOME/.codex}/backups/ai-berkshire-skills/$(date +%Y%m%d-%H%M%S)"
BACKED_UP=0

python3 "$ROOT/scripts/sync-codex-skills.py"
mkdir -p "$DEST"

for skill_dir in "$ROOT"/codex-skills/*; do
  [ -d "$skill_dir" ] || continue
  name="$(basename "$skill_dir")"
  if [ -d "$DEST/$name" ] && ! diff -qr "$skill_dir" "$DEST/$name" >/dev/null 2>&1; then
    mkdir -p "$BACKUP_ROOT"
    cp -R "$DEST/$name" "$BACKUP_ROOT/$name"
    BACKED_UP=1
  fi
  rm -rf "$DEST/$name"
  cp -R "$skill_dir" "$DEST/$name"
done

echo "Installed Codex skills to $DEST"
if [ "$BACKED_UP" -eq 1 ]; then
  echo "Backed up differing installed skills to $BACKUP_ROOT"
fi
echo "Run ./scripts/install-codex-prompts.sh if you want slash-command prompts."
echo "Restart Codex to pick up new skills."
