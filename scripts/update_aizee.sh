#!/usr/bin/env bash
# aiZee Sync Script (POSIX): .ai -> aizee deployment mirror.
# Thin wrapper around scripts/update_aizee.py (the portable implementation).
# Usage: scripts/update_aizee.sh [--dry-run]
set -euo pipefail
cd "$(dirname "$0")/.."
python scripts/update_aizee.py "$@"
