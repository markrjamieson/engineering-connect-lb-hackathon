#!/usr/bin/env python3
"""
Soak test runner for the load balancer.

Sends sustained traffic to a target URL for a configurable duration and/or
request count, then writes a summary log file for comparison across runs.


python tests/soak_test.py --url http://localhost:8080/test --duration-seconds 60 --requests 10000 --concurrency 20 --log-file soak_results_round2.log
"""

import argparse
import collections
import queue
import statistics
import threading
import time
from datetime import datetime
from typing import List, Optional

import requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load balancer soak test")
    parser.add_argument(
        "--url",
        required=True,
        help="Target URL of the load balancer, e.g. http://localhost:8080/test",
    )
    parser.add_argument(
        "--duration-seconds",
        type=int,
        default=60,
        help="Max duration of the test (seconds). Default: 60",
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=5000,
        help="Maximum number of requests to send. Default: 5000",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Number of parallel worker threads. Default: 10",
    )
    parser.add_argument(
        "--method",
        default="GET",
        choices=["GET", "POST", "PUT", "PATCH", "DELETE"],
        help="HTTP method to use. Default: GET",
    )
    parser.add_argument(
        "--body",
        help="Optional request body (for POST/PUT/PATCH). Sent as raw text.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Per-request timeout in seconds. Default: 5.0",
    )
    parser.add_argument(
        "--log-file",
        default="soak_results.log",
        help="Path to write the summary log. Default: soak_results.log",
    )
    return parser.parse_args()


class Metrics:
    def __init__(self) -> None:
        self.latencies: List[float] = []
        self.status_counts: collections.Counter[int] = collections.Counter()
        self.successes = 0
        self.failures = 0
        self.errors: List[str] = []
        self._lock = threading.Lock()

    def record(self, status: Optional[int], latency: Optional[float], error: Optional[str] = None) -> None:
        with self._lock:
            if status is not None:
                self.status_counts[status] += 1
                self.successes += 1
            else:
                self.failures += 1
            if latency is not None:
                self.latencies.append(latency)
            if error:
                self.errors.append(error)

    def summarize(self) -> dict:
        latencies = sorted(self.latencies)
        def percentile(p: float) -> Optional[float]:
            if not latencies:
                return None
            k = (len(latencies) - 1) * p
            f = int(k)
            c = min(f + 1, len(latencies) - 1)
            if f == c:
                return latencies[f]
            return latencies[f] + (latencies[c] - latencies[f]) * (k - f)

        return {
            "count": len(latencies),
            "min": latencies[0] if latencies else None,
            "max": latencies[-1] if latencies else None,
            "avg": statistics.mean(latencies) if latencies else None,
            "p50": percentile(0.50),
            "p95": percentile(0.95),
            "p99": percentile(0.99),
        }


def worker(task_queue: queue.Queue, args: argparse.Namespace, metrics: Metrics, deadline: float) -> None:
    session = requests.Session()
    while time.monotonic() < deadline:
        try:
            task_queue.get_nowait()
        except queue.Empty:
            break

        start = time.monotonic()
        try:
            resp = session.request(
                args.method,
                args.url,
                data=args.body,
                timeout=args.timeout,
            )
            latency = time.monotonic() - start
            metrics.record(resp.status_code, latency)
        except Exception as exc:  # broad to capture timeouts/connection errors
            latency = time.monotonic() - start
            metrics.record(None, latency, error=str(exc))
        finally:
            task_queue.task_done()


def format_latency(value: Optional[float]) -> str:
    return f"{value*1000:.2f} ms" if value is not None else "n/a"


def run_soak() -> None:
    args = parse_args()

    start_ts = datetime.utcnow()
    deadline = time.monotonic() + args.duration_seconds

    task_queue: queue.Queue = queue.Queue()
    for _ in range(args.requests):
        task_queue.put(1)

    metrics = Metrics()

    threads = []
    for _ in range(max(1, args.concurrency)):
        t = threading.Thread(target=worker, args=(task_queue, args, metrics, deadline), daemon=True)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    end_ts = datetime.utcnow()
    elapsed = (end_ts - start_ts).total_seconds()
    latency_summary = metrics.summarize()
    rps = metrics.successes / elapsed if elapsed > 0 else 0

    lines = [
        "=== Soak Test Summary ===",
        "",
        "--- Test Configuration ---",
        f"Target URL       : {args.url}",
        f"HTTP Method      : {args.method}",
        f"Request Body     : {'provided' if args.body else 'none'}",
        f"Max Duration     : {args.duration_seconds} seconds",
        f"Max Requests     : {args.requests}",
        f"Concurrency      : {args.concurrency} threads",
        f"Request Timeout  : {args.timeout} seconds",
        f"Log File         : {args.log_file}",
        "",
        "--- Test Results ---",
        f"Start (UTC)      : {start_ts.isoformat()}",
        f"End   (UTC)      : {end_ts.isoformat()}",
        f"Actual Duration  : {elapsed:.2f} s (target {args.duration_seconds}s)",
        f"Requests         : attempted {args.requests}, successes {metrics.successes}, failures {metrics.failures}",
        f"Status codes     : {dict(metrics.status_counts)}",
        f"RPS (approx)     : {rps:.2f}",
        "",
        "Latencies:",
        f"  count : {latency_summary['count']}",
        f"  min   : {format_latency(latency_summary['min'])}",
        f"  avg   : {format_latency(latency_summary['avg'])}",
        f"  p50   : {format_latency(latency_summary['p50'])}",
        f"  p95   : {format_latency(latency_summary['p95'])}",
        f"  p99   : {format_latency(latency_summary['p99'])}",
        f"  max   : {format_latency(latency_summary['max'])}",
    ]

    if metrics.errors:
        lines.append(f"Errors (sample of up to 5): {metrics.errors[:5]}")

    output = "\n".join(lines)
    print(output)

    with open(args.log_file, "a", encoding="utf-8") as f:
        f.write("\n".join([
            "",
            "#" * 32,
            output,
        ]))


if __name__ == "__main__":
    run_soak()

