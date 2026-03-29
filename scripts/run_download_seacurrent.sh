#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${PROJECT_ROOT}/logs"
mkdir -p "${LOG_DIR}"

python3 "${PROJECT_ROOT}/scripts/download_seacurrent_nc.py" \
  --output "${PROJECT_ROOT}/data/nc_files" \
  >> "${LOG_DIR}/download_seacurrent.log" 2>&1
