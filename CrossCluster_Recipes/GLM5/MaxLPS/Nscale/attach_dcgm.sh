#!/bin/bash
# Attach one native DCGM collector to every node of a running srtctl job.
# Usage: attach_dcgm.sh <job_id> <node_count> <output_dir>
set -euo pipefail

JOB_ID=${1:?job ID required}
NODE_COUNT=${2:?node count required}
OUTDIR=${3:?output directory required}
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
COLLECTOR="${SCRIPT_DIR}/collect_dcgm_node.sh"

[[ "${NODE_COUNT}" =~ ^[1-9][0-9]*$ ]] || {
  echo "node_count must be a positive integer" >&2
  exit 2
}
[[ -x "${COLLECTOR}" ]] || {
  echo "collector is missing or not executable: ${COLLECTOR}" >&2
  exit 2
}

mkdir -p "${OUTDIR}"
srun --overlap --jobid="${JOB_ID}" --nodes="${NODE_COUNT}" \
  --ntasks="${NODE_COUNT}" --ntasks-per-node=1 \
  "${COLLECTOR}" "${OUTDIR}" \
  >"${OUTDIR}/srun_attach.log" 2>&1
