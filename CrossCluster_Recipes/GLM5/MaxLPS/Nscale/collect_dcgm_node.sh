#!/bin/bash
# Run inside one allocated GB300 node and sample native dcgm-exporter metrics.
set -euo pipefail

OUTDIR=${1:?output directory required}
HOST=$(hostname)
PORT=${DCGM_EXPORTER_PORT:-19400}
INTERVAL_MS=${DCGM_INTERVAL_MS:-1000}
METRICS="${OUTDIR}/${HOST}_dcgm.prom"
EXPORTER_LOG="${OUTDIR}/${HOST}_dcgm_exporter.log"

mkdir -p "${OUTDIR}"
command -v dcgm-exporter >/dev/null || {
  echo "dcgm-exporter is not installed or not on PATH" >&2
  exit 1
}
command -v curl >/dev/null || {
  echo "curl is not installed or not on PATH" >&2
  exit 1
}

dcgm-exporter --collect-interval="${INTERVAL_MS}" --address ":${PORT}" \
  >"${EXPORTER_LOG}" 2>&1 &
EXPORTER_PID=$!
trap 'kill "${EXPORTER_PID}" 2>/dev/null || true; wait "${EXPORTER_PID}" 2>/dev/null || true' EXIT

for _ in $(seq 1 30); do
  curl -fsS "http://127.0.0.1:${PORT}/metrics" >/dev/null 2>&1 && break
  kill -0 "${EXPORTER_PID}" 2>/dev/null || {
    echo "dcgm-exporter exited before becoming ready; see ${EXPORTER_LOG}" >&2
    exit 1
  }
  sleep 1
done
curl -fsS "http://127.0.0.1:${PORT}/metrics" >/dev/null

REGEX='^DCGM_FI_(DEV_(POWER_USAGE|TOTAL_ENERGY_CONSUMPTION|GPU_UTIL|GPU_TEMP|MEMORY_TEMP|SM_CLOCK|MEM_CLOCK|CLOCK_THROTTLE_REASONS|POWER_VIOLATION|THERMAL_VIOLATION|BOARD_LIMIT_VIOLATION|FB_USED|FB_FREE)|PROF_(SM_ACTIVE|SM_OCCUPANCY|DRAM_ACTIVE|PIPE_TENSOR_ACTIVE|NVLINK_RX_BYTES|NVLINK_TX_BYTES))'

printf 'GLM5_GB300_DCGM_TELEMETRY_V1\nnode=%s\ninterval_ms=%s\n' \
  "${HOST}" "${INTERVAL_MS}" >"${METRICS}"
while kill -0 "${EXPORTER_PID}" 2>/dev/null; do
  printf 'SAMPLE_BEGIN ts=%s node=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${HOST}" >>"${METRICS}"
  curl -fsS "http://127.0.0.1:${PORT}/metrics" 2>/dev/null \
    | grep -E "${REGEX}" >>"${METRICS}" || true
  printf 'SAMPLE_END\n' >>"${METRICS}"
  sleep 1
done
