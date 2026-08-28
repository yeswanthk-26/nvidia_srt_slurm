# OCI-AGA GLM-5 GB300 selected-point telemetry reference

This directory is a portable, read-only reference for independently checking
the OCI-AGA power numbers used by the Nscale GLM-5 bring-up. It contains only
the selected benchmark windows and no credentials, model data, unrelated logs,
or user-specific paths.

Run the analysis from this directory:

```bash
python3 analyze_power.py --verify
```

`analyze_power.py` uses only the Python standard library. It reads the bundled
gzip-compressed CSV, prints machine-readable JSON, and exits nonzero if a
calculated result differs from `expected_results.json`.

## Evidence provenance

The portable CSV was extracted from `DCGM_FI_DEV_POWER_USAGE` rows in the
following preserved jobs:

- Job 589394, nodes `nvl72d101-T[07-12]`, selected 24-GPU concurrency-1
  point. Source artifacts:
  `outputs_glm5_24gpu_minlat/589394/`.
- Job 589520, nodes `nvl72d101-T[07-14]`, selected 32-GPU concurrency-256
  point. Source artifacts:
  `outputs_glm5_32gpu_hightpt/589520/`.

The source recipes are `local_runs/glm5_24gpu_singledomain.yaml` and
`local_runs/glm5_32gpu_singledomain.yaml`. The generated `sbatch_script.sh`,
`recipe.lock.yaml`, `logs/sweep_*.log`, `logs/benchmark.out`, selected
`results_concurrency_*.json`, and per-node `logs/dcgm/*_dcgm.prom` files were
cross-checked.

Exact software recorded by the lockfiles:

- Model `nvidia/GLM5-NVFP4`, revision
  `dc54ff55a7e9e71b85db953d8bc22eca894b44c6`
- Container
  `nvcr.io/nvidia/ai-dynamo/tensorrtllm-runtime:1.1.0-dev.3`
- TensorRT-LLM `1.3.0rc11`, Dynamo `1.1.0.dev3`
- Driver `580.167.08`, CUDA compiler `13.1.115`, NCCL `2.29.2`

Both points used NVFP4 weights, FP8 KV cache, 8192 input tokens, 1024 requested
output tokens, random-range ratio 0.8, infinite request rate, `ignore_eos`,
four TP2/EP2 prefill workers on T07-T08, and TP8/EP8 MNNVL decode workers on
paired nodes. `UCX_TLS=rc,dc,ud,cuda_copy,cuda_ipc,tcp` and
`stream_interval=100` were set.

The 24-GPU point used two decode workers on T09-T12,
`max_batch_size=max_num_tokens=1`, concurrency 1, and 16 prompts. The 32-GPU
point used three decode workers on T09-T14,
`max_batch_size=max_num_tokens=64`, concurrency 256, and 4096 prompts.

## Active-window definition

Benchmark logs use PDT while DCGM sample markers use UTC. SA-Bench did not emit
a wall-clock timestamp on the exact line where the main run began. The selected
window end is therefore the second-resolution `date` in the result JSON,
converted to UTC; the start is that end minus the reported monotonic benchmark
duration. Integer-second DCGM markers inside the bounds are included.

- Job 589394 c=1:
  `2026-08-27T13:45:38.630527Z` through
  `2026-08-27T13:48:37Z`, duration `178.36947308806702 s`.
  The command launched at `06:45:22 PDT`; the approximately 16.6 seconds before
  the derived main window were the command's internal single-prompt test.
- Job 589520 c=256:
  `2026-08-27T14:24:52.738635Z` through
  `2026-08-27T14:32:31Z`, duration `458.2613651610445 s`.
  The command launched at `07:24:22 PDT`; the approximately 30.7 seconds before
  the derived main window were the internal test. The human-readable completion
  line followed at `07:32:32 PDT`.

The package excludes service/model startup, request-rate-250 pre-runs, internal
single-prompt tests, the 24-GPU c=2 point, and the 32-GPU c=64/c=128 points.
Window placement has approximately one-second uncertainty because the result
date has only whole-second resolution.

## Power-limit conclusion

The source recipes, exact generated scripts, lockfiles, launch commands,
environment dumps, and job logs contain no `nvidia-smi -pl`, `dcgmi` limit,
power-cap setting, DPS control, or MaxLPS control. This supports, with high
confidence, the limited statement **no software power cap was requested by the
preserved recipe or launch path**.

It does not prove that the GPUs were effectively uncapped. The exact collector
selected `POWER_USAGE`, energy, utilization, clocks, violation counters, and
temperatures, but did not select `DCGM_FI_DEV_POWER_MGMT_LIMIT` or preserve
equivalent current/default/max limit output. Effective limits for jobs 589394
and 589520 are therefore unknown.

The later diagnostic job 596989 reportedly observed 1400 W current, default,
and maximum limits on four GPUs of one allocated node. That is useful
environmental evidence, but it is not contemporaneous exact-run evidence and
must not be assigned retrospectively to these jobs.

## Coverage and cadence

The source collector configured `dcgm-exporter --collect-interval=1000` and
polled the exporter approximately once per second.

- Job 589394 captured all six expected nodes and four distinct GPUs per node.
  Each node has 1,038-1,043 samples over approximately
  `13:35:20Z-13:53:31Z`.
- Job 589520 captured all eight expected nodes and four distinct GPUs per node.
  Each node has 1,857-1,876 samples over approximately
  `14:00:38Z-14:33:21Z`.
- Per-node median and p95 inter-sample gaps are one second; maximum gap is two
  seconds. Approximately 95.1-95.7% of adjacent markers are exactly one second
  apart.

Within the selected windows, all integer seconds have at least one GPU sample,
but only 142/179 seconds for job 589394 and 321/459 seconds for job 589520 have
all expected GPUs. GPU-row completeness is 4,132/4,296 (96.18%) and
14,064/14,688 (95.75%), respectively.

## Aggregations and audited results

Percentiles use deterministic R-7/NumPy linear interpolation:
`rank=(n-1)*p`, with linear interpolation between adjacent sorted values.

### Pooled GPU-time

Every observed GPU value in the selected window is one observation. Incomplete
timestamps remain included.

- 24 GPU c=1, 4,132 values:
  mean `280.540 W`, p95 `365.157 W`, max `833.268 W`.
  - Prefill: 1,376 values, mean `247.932 W`, p95 `245.923 W`,
    max `833.268 W`.
  - Decode: 2,756 values, mean `296.821 W`, p95 `365.755 W`,
    max `370.261 W`.
- 32 GPU c=256, 14,064 values:
  mean `678.772 W`, p95 `1080.557 W`, max `1131.289 W`.
  - Prefill: 3,512 values, mean `891.893 W`, p95 `1099.853 W`,
    max `1131.289 W`.
  - Decode: 10,552 values, mean `607.840 W`, p95 `633.130 W`,
    max `664.943 W`.

The unusual 24-GPU prefill mean above its p95 is real: most values are near
240 W, while a small number of approximately 800 W observations raise the
mean and max.

### Synchronized per-second fleet-average

Only timestamps containing exactly one value from every expected GPU are kept.
All GPUs are averaged at each surviving timestamp; mean, p95, and max are then
calculated over those per-second averages. Role results use the same globally
complete timestamp set.

- 24 GPU c=1, 142 timestamps:
  mean `280.630 W/GPU`, p95 `292.755 W/GPU`, max `309.181 W/GPU`.
  - Prefill: mean `247.274`, p95 `294.155`, max `322.435 W/GPU`.
  - Decode: mean `297.308`, p95 `302.698`, max `302.906 W/GPU`.
- 32 GPU c=256, 321 timestamps:
  mean `677.065 W/GPU`, p95 `721.405 W/GPU`, max `735.980 W/GPU`.
  - Prefill: mean `885.975`, p95 `1058.822`, max `1090.495 W/GPU`.
  - Decode: mean `607.428`, p95 `623.186`, max `624.630 W/GPU`.

This second method reproduces the previously reported OCI values rounded to
one decimal: 280.6/292.8 W/GPU and 677.1/721.4 W/GPU. The narrow p95 is a p95
of the cross-GPU fleet average, not a per-GPU power p95. Cross-GPU averaging
suppresses short prefill excursions, and globally complete filtering discards
37 and 138 otherwise represented seconds.

Performance from the same selected result files is:

- 24 GPU c=1: `83.125 output tok/s`, `885.820 ms` median TTFT.
- 32 GPU c=256: `8236.217 output tok/s`, `7049.453 ms` median TTFT.

## Nscale mirroring checklist

For a defensible cross-cluster comparison, the Nscale agent should:

1. Match the model revision, container/runtime versions, TP/EP layout, worker
   counts, batch/token limits, benchmark seed and random-input settings, prompt
   counts, `ignore_eos`, and infinite request rate.
2. Keep each deployment inside one validated NVL72 domain. Do not copy the OCI
   node names; use Nscale-approved placement.
3. Record explicit UTC markers at the exact start and end of the main run.
   Exclude endpoint probes, warmups, internal single-prompt tests, model loading,
   and other sweep points.
4. Sample every GPU at one-second cadence and preserve node, GPU identity, role,
   timestamp, and raw board power. Report missing and duplicate samples.
5. Capture effective/current, requested, default, minimum, and maximum power
   limits before, during, and after the selected window. Include
   `DCGM_FI_DEV_POWER_MGMT_LIMIT` or equivalent independently preserved output.
6. Calculate and report both definitions in this package. Do not compare a
   pooled Nscale p95 with the synchronized OCI p95.
7. Use one explicit missing-data policy. For synchronized comparison, require
   every expected GPU at a timestamp and report the retained fraction. Also
   retain pooled results so individual excursions remain visible.
8. Report prefill and decode separately using the actual deployment mapping.
9. Preserve exact software fingerprints, benchmark result JSON, generated
   launch configuration, and telemetry collection settings.
10. Use TPOT for token-level latency comparison. With `stream_interval=100`,
    SA-Bench ITL measures intervals between streamed chunks, not individual
    tokens.

The supplied Nscale values can only be compared directly after confirming their
window and aggregation definition. If they are pooled GPU-time values, the
matching OCI references are 280.540/365.157/833.268 W for 24 GPUs and
678.772/1080.557/1131.289 W for 32 GPUs.
