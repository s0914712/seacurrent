#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${PROJECT_ROOT}/logs"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/download_and_convert_seacurrent.log"

{
  echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] START"
  python3 "${PROJECT_ROOT}/scripts/download_seacurrent_nc.py" --output "${PROJECT_ROOT}/data/nc_files"
  python3 "${PROJECT_ROOT}/scripts/convert_seacurrent_for_drift.py" \
    --input-dir "${PROJECT_ROOT}/data/nc_files" \
    --output-dir "${PROJECT_ROOT}/data/nc_converted"
  echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] END"
} >> "${LOG_FILE}" 2>&1
