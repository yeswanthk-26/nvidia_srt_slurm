# GLM-5 GB300 MaxLPS — Nscale bring-up

This package carries the OCI-AGA validated GLM-5 NVFP4 TRT-LLM/Dynamo
operating points into the Nscale Iceland GB300 environment.

## Selected workloads

| Class | Recipe | Nodes | GPUs | Operating point |
| --- | --- | ---: | ---: | --- |
| High throughput | `glm5_32gpu_high_throughput.yaml` | 8 | 32 | 8K/1K, concurrency 256 |
| Min latency | `glm5_24gpu_min_latency.yaml` | 6 | 24 | 8K/1K, concurrency 1 |

OCI-AGA single-instance validation anchors:

- 32 GPUs: 8,236 output tok/s, 7.049 s median TTFT, 677.1 W/GPU
  mean power, 721.4 W/GPU sampled p95.
- 24 GPUs: 83.1 output tok/s, 0.886 s median TTFT, 280.6 W/GPU
  mean power, 292.8 W/GPU sampled p95.

These are cross-validation anchors, not expected Nscale acceptance values.

## Required Nscale preflight

Do not start the scale test until all of the following are confirmed:

1. Identify the GB300 partition, node names, NVL72 domains, and scheduler
   topology behavior.
2. Add a site-approved placement constraint to each recipe. Decode TP8/EP8
   uses MNNVL; all nodes of an instance must stay within one NVL72 domain.
   Do not copy the OCI `nvl72d101-*` nodelist.
3. Confirm access to `nvidia/GLM5-NVFP4`,
   `nvcr.io/nvidia/ai-dynamo/tensorrtllm-runtime:1.1.0-dev.3`, NGC/Hugging
   Face credentials, and the repository setup script.
4. Confirm `srtctl`, NATS/ETCD assets, Enroot/Pyxis, UCX, and the configured
   shared storage paths work on Nscale.
5. Confirm `dcgm-exporter` and `curl` are available on every compute node and
   that an overlapping `srun` step is permitted.
6. Dry-run both YAML files, then run one 24-GPU and one 32-GPU smoke test.
   Check logs for UCX bind failures, MNNVL domain warnings, MPI failures, and
   KV-cache transfer timeouts.
7. Verify every allocated node emits four distinct GPU series in its `.prom`
   telemetry file.

`UCX_TLS=rc,dc,ud,cuda_copy,cuda_ipc,tcp` was required on OCI-AGA. Keep it
for the first Nscale smoke test, but treat it as a configuration to validate
rather than an Nscale-specific requirement. Do not set `UCX_NET_DEVICES`
unless Nscale networking owners require and validate it.

## Smoke-test commands

From the repository root:

```bash
srtctl dry-run -f CrossCluster_Recipes/GLM5/MaxLPS/Nscale/glm5_24gpu_min_latency.yaml
srtctl dry-run -f CrossCluster_Recipes/GLM5/MaxLPS/Nscale/glm5_32gpu_high_throughput.yaml

srtctl apply -f CrossCluster_Recipes/GLM5/MaxLPS/Nscale/glm5_24gpu_min_latency.yaml
srtctl apply -f CrossCluster_Recipes/GLM5/MaxLPS/Nscale/glm5_32gpu_high_throughput.yaml
```

After each job is running, attach telemetry using its actual job ID:

```bash
chmod +x CrossCluster_Recipes/GLM5/MaxLPS/Nscale/*.sh
CrossCluster_Recipes/GLM5/MaxLPS/Nscale/attach_dcgm.sh <24GPU_JOB_ID> 6 <OUTPUT_DIR>
CrossCluster_Recipes/GLM5/MaxLPS/Nscale/attach_dcgm.sh <32GPU_JOB_ID> 8 <OUTPUT_DIR>
```

Run the attach command in a separate terminal or background process. It exits
when the allocation ends.

## Scale plan

- Baseline: 3 high-throughput instances plus 2 min-latency instances =
  36 nodes / 144 GPUs.
- MaxLPS: 4 high-throughput instances plus 3 min-latency instances =
  50 nodes / 200 GPUs, 38.9% more GPUs.
- Measurement window: three hours for each scenario after all model servers
  are healthy.

The supplied recipes execute one selected benchmark batch. The final scale
run needs an orchestration method that keeps each deployment alive and sends
successive benchmark batches to the same endpoint for three hours. Do not
loop `srtctl apply`, because that would repeatedly reload the model and would
not represent a continuous workload.

Capture per-instance throughput, TTFT, TPOT, E2E latency, request failures,
GPU utilization, board power, energy, clocks, throttle reasons, temperatures,
and NVLink counters. Also capture aggregate rack/facility power from Nscale
with synchronized UTC timestamps.

The recipes currently use `stream_interval: 100`. SA-Bench ITL therefore
represents intervals between streamed chunks, not individual-token ITL. Use
TPOT for the current token-level comparison, or separately validate
`stream_interval: 1` if the test plan requires true token-level ITL.
