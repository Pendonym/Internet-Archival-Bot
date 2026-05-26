#!/usr/bin/env bash
set -euo pipefail

find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true