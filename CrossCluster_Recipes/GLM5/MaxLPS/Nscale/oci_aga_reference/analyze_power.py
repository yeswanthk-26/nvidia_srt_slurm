#!/usr/bin/env python3
"""Analyze the portable OCI-AGA selected-window GPU power samples.

Only the Python standard library is required. Percentiles use the deterministic
R-7/NumPy "linear" definition: rank=(n-1)*p with linear interpolation between
the adjacent ordered observations.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable


REQUIRED_COLUMNS = {
    "job_id",
    "workload",
    "timestamp_utc",
    "node",
    "gpu",
    "role",
    "power_w",
}
ROLES = ("prefill", "decode")


def percentile_linear(values: Iterable[float], probability: float) -> float:
    """Return an R-7 linear percentile for a non-empty sequence."""
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot calculate a percentile of an empty sequence")
    rank = (len(ordered) - 1) * probability
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    fraction = rank - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def summary(values: list[float]) -> dict[str, float | int]:
    if not values:
        raise ValueError("cannot summarize an empty sequence")
    return {
        "n": len(values),
        "mean_w": statistics.fmean(values),
        "p95_w": percentile_linear(values, 0.95),
        "max_w": max(values),
    }


def open_csv(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", newline="")
    return path.open("r", encoding="utf-8", newline="")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp lacks timezone: {value}")
    return parsed.astimezone(timezone.utc)


def expected_integer_seconds(start: str, end: str) -> int:
    start_dt = parse_utc(start)
    end_dt = parse_utc(end)
    first = start_dt.replace(microsecond=0)
    if first < start_dt:
        first += timedelta(seconds=1)
    last = end_dt.replace(microsecond=0)
    if last > end_dt:
        last -= timedelta(seconds=1)
    return max(0, int((last - first).total_seconds()) + 1)


def analyze(csv_path: Path, expected: dict) -> dict:
    workloads = {
        item["workload"]: item for item in expected["workloads"]
    }
    rows_by_workload: dict[str, list[dict[str, str]]] = defaultdict(list)

    with open_csv(csv_path) as stream:
        reader = csv.DictReader(stream)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"CSV is missing columns: {sorted(missing)}")
        for row in reader:
            workload = row["workload"]
            if workload not in workloads:
                raise ValueError(f"unexpected workload in CSV: {workload}")
            rows_by_workload[workload].append(row)

    results: dict[str, object] = {
        "schema_version": 1,
        "input_file": csv_path.name,
        "input_sha256": sha256_file(csv_path),
        "quantile_method": (
            "R-7 linear interpolation: rank=(n-1)*p; p=0.95"
        ),
        "workloads": {},
    }

    for workload, metadata in workloads.items():
        rows = rows_by_workload.get(workload, [])
        if not rows:
            raise ValueError(f"no rows found for workload {workload}")

        expected_participants = {
            (node, str(gpu))
            for node in metadata["expected_nodes"]
            for gpu in range(metadata["gpus_per_node"])
        }
        expected_role_by_node = {
            node: role
            for role, nodes in metadata["roles"].items()
            for node in nodes
        }
        window_start = parse_utc(metadata["active_window_utc"]["start"])
        window_end = parse_utc(metadata["active_window_utc"]["end"])
        by_timestamp: dict[str, dict[tuple[str, str], dict[str, str]]] = (
            defaultdict(dict)
        )

        for row in rows:
            if row["job_id"] != metadata["job_id"]:
                raise ValueError(
                    f"{workload}: unexpected job_id {row['job_id']}"
                )
            participant = (row["node"], row["gpu"])
            if participant not in expected_participants:
                raise ValueError(
                    f"{workload}: unexpected participant {participant}"
                )
            if row["role"] not in ROLES:
                raise ValueError(f"{workload}: invalid role {row['role']}")
            if row["role"] != expected_role_by_node[row["node"]]:
                raise ValueError(
                    f"{workload}: wrong role {row['role']} for {row['node']}"
                )
            timestamp = row["timestamp_utc"]
            timestamp_dt = parse_utc(timestamp)
            if not window_start <= timestamp_dt <= window_end:
                raise ValueError(
                    f"{workload}: timestamp outside active window: {timestamp}"
                )
            power = float(row["power_w"])
            if not math.isfinite(power) or power < 0.0:
                raise ValueError(
                    f"{workload}: invalid power value {row['power_w']}"
                )
            if participant in by_timestamp[timestamp]:
                raise ValueError(
                    f"{workload}: duplicate {participant} at {timestamp}"
                )
            by_timestamp[timestamp][participant] = row

        complete = {
            timestamp: samples
            for timestamp, samples in by_timestamp.items()
            if set(samples) == expected_participants
        }
        expected_seconds = expected_integer_seconds(
            metadata["active_window_utc"]["start"],
            metadata["active_window_utc"]["end"],
        )
        expected_rows = expected_seconds * len(expected_participants)

        pooled_values = [float(row["power_w"]) for row in rows]
        pooled_roles = {
            role: summary(
                [
                    float(row["power_w"])
                    for row in rows
                    if row["role"] == role
                ]
            )
            for role in ROLES
        }

        fleet_averages = [
            statistics.fmean(float(row["power_w"]) for row in samples.values())
            for samples in complete.values()
        ]
        synchronized_roles = {}
        for role in ROLES:
            role_averages = [
                statistics.fmean(
                    float(row["power_w"])
                    for row in samples.values()
                    if row["role"] == role
                )
                for samples in complete.values()
            ]
            synchronized_roles[role] = summary(role_averages)

        results["workloads"][workload] = {
            "job_id": metadata["job_id"],
            "active_window_utc": metadata["active_window_utc"],
            "expected_gpu_count": len(expected_participants),
            "pooled_gpu_time": {
                "overall": summary(pooled_values),
                "roles": pooled_roles,
            },
            "synchronized_per_second_fleet_average": {
                "overall": summary(fleet_averages),
                "roles": synchronized_roles,
            },
            "completeness": {
                "expected_integer_seconds": expected_seconds,
                "timestamps_with_any_samples": len(by_timestamp),
                "globally_complete_timestamps": len(complete),
                "incomplete_timestamps": len(by_timestamp) - len(complete),
                "complete_timestamp_fraction": (
                    len(complete) / expected_seconds
                ),
                "observed_gpu_samples": len(rows),
                "expected_gpu_samples": expected_rows,
                "gpu_sample_fraction": len(rows) / expected_rows,
            },
        }

    return results


def compare_expected(actual: object, expected: object, path: str = "") -> list[str]:
    errors: list[str] = []
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path}: expected object, got {type(actual).__name__}"]
        for key, value in expected.items():
            child = f"{path}.{key}" if path else key
            if key not in actual:
                errors.append(f"{child}: missing")
            else:
                errors.extend(compare_expected(actual[key], value, child))
    elif isinstance(expected, float):
        if not isinstance(actual, (int, float)) or not math.isclose(
            float(actual), expected, rel_tol=1e-12, abs_tol=1e-9
        ):
            errors.append(f"{path}: expected {expected!r}, got {actual!r}")
    elif actual != expected:
        errors.append(f"{path}: expected {expected!r}, got {actual!r}")
    return errors


def main() -> int:
    package_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "csv",
        nargs="?",
        type=Path,
        default=package_dir / "oci_aga_selected_power_samples.csv.gz",
    )
    parser.add_argument(
        "--expected",
        type=Path,
        default=package_dir / "expected_results.json",
        help="metadata and expected analysis results",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="fail if calculated results differ from expected_analysis",
    )
    args = parser.parse_args()

    with args.expected.open("r", encoding="utf-8") as stream:
        expected = json.load(stream)
    actual = analyze(args.csv, expected)
    print(json.dumps(actual, indent=2, sort_keys=True))

    if args.verify:
        errors = []
        if actual["input_sha256"] != expected["dataset_sha256"]:
            errors.append(
                "input_sha256: expected "
                f"{expected['dataset_sha256']!r}, "
                f"got {actual['input_sha256']!r}"
            )
        errors.extend(compare_expected(
            actual["workloads"], expected["expected_analysis"]["workloads"]
        ))
        if errors:
            for error in errors:
                print(f"VERIFY ERROR: {error}", file=sys.stderr)
            return 1
        print("VERIFY OK: calculated results match expected_results.json", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
