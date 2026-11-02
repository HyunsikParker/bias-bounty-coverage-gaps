#!/usr/bin/env python3
"""Shared, dependency-light helpers for the local DuckDB pipeline."""

from __future__ import annotations

import json
import os
import re
import resource
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"
EXTENSIONS = WORK / "duckdb_extensions"
TEMP = WORK / "duckdb_tmp"

REGIONS = (
    "maricopa-az",
    "northern-ca",
    "eastern-ok",
    "south-central-tx",
    "eastern-wa",
)
SCORED_REGIONS = REGIONS  # eastern-wa is scored too: Zindi rejected a 4-region file for missing 53xxx GEOIDs


def sql_path(path: Path) -> str:
    """Return a safely quoted absolute path for a DuckDB SQL literal."""
    return str(path.resolve()).replace("'", "''")


def prelude(spatial: bool = True) -> str:
    statements = [
        f"SET extension_directory='{sql_path(EXTENSIONS)}'",
        "SET memory_limit='6GB'",
        "SET threads=4",
        f"SET temp_directory='{sql_path(TEMP)}'",
        "SET preserve_insertion_order=false",
    ]
    if spatial:
        statements.append("LOAD spatial")
    return ";\n".join(statements) + ";\n"


def ensure_runtime() -> None:
    WORK.mkdir(exist_ok=True)
    EXTENSIONS.mkdir(parents=True, exist_ok=True)
    TEMP.mkdir(parents=True, exist_ok=True)
    probe = subprocess.run(
        [
            "duckdb",
            "-c",
            f"SET extension_directory='{sql_path(EXTENSIONS)}'; LOAD spatial; SELECT 1;",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    if probe.returncode == 0:
        return
    install = subprocess.run(
        [
            "duckdb",
            "-c",
            f"SET extension_directory='{sql_path(EXTENSIONS)}'; INSTALL spatial; LOAD spatial; SELECT 1;",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    if install.returncode != 0:
        raise RuntimeError("DuckDB spatial installation failed: " + install.stderr.strip())


def run_duckdb(sql: str, *, json_output: bool = False) -> tuple[str, dict[str, Any]]:
    """Run one bounded DuckDB process and return output plus measured resources."""
    command = ["duckdb"]
    if json_output:
        command.append("-json")
    command.extend(["-c", sql])
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.monotonic()
    proc = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "LC_ALL": "C"},
    )
    elapsed = time.monotonic() - started
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    if proc.returncode != 0:
        message = proc.stderr.strip() or proc.stdout.strip() or "unknown DuckDB error"
        raise RuntimeError(message)
    # ru_maxrss is bytes on macOS and KiB on Linux. It is the largest child seen,
    # which is the relevant safety bound because regions run sequentially.
    rss = after.ru_maxrss
    if not sys.platform.startswith("darwin"):
        rss *= 1024
    metrics = {
        "elapsed_seconds": round(elapsed, 6),
        "max_child_rss_bytes": int(rss),
        "user_cpu_seconds_delta": round(after.ru_utime - before.ru_utime, 6),
        "system_cpu_seconds_delta": round(after.ru_stime - before.ru_stime, 6),
    }
    return proc.stdout, metrics


def query_json(sql: str) -> list[dict[str, Any]]:
    output, _ = run_duckdb(sql, json_output=True)
    if not output.strip():
        return []
    return json.loads(output)


def atomic_copy_query(query: str, destination: Path) -> dict[str, Any]:
    """COPY a query to Parquet and atomically replace the requested destination."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(
        f".{destination.name}.{os.getpid()}.{time.time_ns()}.tmp"
    )
    statement = (
        prelude()
        + f"COPY ({query}) TO '{sql_path(temporary)}' "
        + "(FORMAT PARQUET, COMPRESSION ZSTD);"
    )
    try:
        _, metrics = run_duckdb(statement)
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    metrics["output_bytes"] = destination.stat().st_size
    return metrics


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def duckdb_version() -> str:
    proc = subprocess.run(
        ["duckdb", "--version"], cwd=ROOT, text=True, capture_output=True, check=True
    )
    match = re.search(r"v?([0-9]+(?:\.[0-9]+)+)", proc.stdout)
    return match.group(1) if match else proc.stdout.strip()
