# -*- coding: utf-8 -*-
"""
API performance benchmark for the Procurement Intelligence Agent.

Measures concurrent multi-agent task execution across:
  - GET  /health                       (baseline)
  - GET  /metrics                      (dashboard read, DB query)
  - GET  /audit-log                    (audit trail read)
  - POST /procurement/request          (full pipeline: scoring + routing)
  - POST /procurement/supplier/score   (supplier scoring agent)

Read and write endpoints run in separate worker pools so heavy pipeline
work does not inflate dashboard latency numbers.

Usage:
    python benchmark.py                         # 20 users, 60s
    python benchmark.py --users 50 --duration 120
    python benchmark.py --endpoint http://localhost:8000
    python benchmark.py --users 20 --duration 30 --quick
"""

import argparse
import asyncio
import itertools
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import httpx

DEFAULT_BASE_URL = "http://localhost:8000"

# ---------------------------------------------------------------------------
# Realistic test data — same suppliers as test-procurement.sh
# ---------------------------------------------------------------------------

PURCHASE_REQUESTS = [
    {"requester": "John Smith",        "supplier_name": "TechCorp Solutions",         "category": "IT Services",       "value": 15000, "description": "Cloud infrastructure migration",     "pilot_team": "pilot-alpha"},
    {"requester": "Sarah Johnson",     "supplier_name": "Global Parts Manufacturing", "category": "Manufacturing",      "value": 45000, "description": "Raw material procurement for Q2",    "pilot_team": "pilot-alpha"},
    {"requester": "Michael Chen",      "supplier_name": "Premium Logistics Inc",      "category": "Logistics",          "value": 8500,  "description": "International shipping",             "pilot_team": "pilot-beta"},
    {"requester": "Emma Wilson",       "supplier_name": "Enterprise Security Group",  "category": "Security Services",  "value": 22000, "description": "Cybersecurity audit",                "pilot_team": "pilot-beta"},
    {"requester": "David Brown",       "supplier_name": "DataFlow Analytics",         "category": "Data Services",      "value": 35000, "description": "Data pipeline implementation",       "pilot_team": "pilot-alpha"},
    {"requester": "Lisa Garcia",       "supplier_name": "Office Solutions Ltd",       "category": "Facilities",         "value": 5500,  "description": "Office equipment procurement",       "pilot_team": "pilot-beta"},
    {"requester": "Robert Taylor",     "supplier_name": "ConsultPro Advisors",        "category": "Consulting",         "value": 28000, "description": "Business optimization consultation", "pilot_team": "pilot-alpha"},
    {"requester": "Michelle Martinez", "supplier_name": "Compliance & Legal Experts", "category": "Legal",              "value": 12000, "description": "Regulatory compliance review",       "pilot_team": "pilot-beta"},
]

SUPPLIER_SCORE_REQUESTS = [
    {"supplier_name": "TechCorp Solutions",         "category": "IT Services",       "pilot_team": "pilot-alpha"},
    {"supplier_name": "Global Parts Manufacturing", "category": "Manufacturing",      "pilot_team": "pilot-alpha"},
    {"supplier_name": "Premium Logistics Inc",      "category": "Logistics",          "pilot_team": "pilot-beta"},
    {"supplier_name": "Enterprise Security Group",  "category": "Security Services",  "pilot_team": "pilot-beta"},
    {"supplier_name": "DataFlow Analytics",         "category": "Data Services",      "pilot_team": "pilot-alpha"},
]


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------

@dataclass
class RequestResult:
    endpoint: str
    method: str
    status_code: int
    latency_ms: float
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None and 200 <= self.status_code < 400


@dataclass
class EndpointStats:
    endpoint: str
    results: list = field(default_factory=list)

    def add(self, r: RequestResult):
        self.results.append(r)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def successes(self) -> int:
        return sum(1 for r in self.results if r.success)

    @property
    def failures(self) -> int:
        return self.total - self.successes

    @property
    def success_rate(self) -> float:
        return (self.successes / self.total * 100) if self.total else 0.0

    def _latencies(self):
        return sorted(r.latency_ms for r in self.results if r.success)

    def percentile(self, p: float) -> float:
        lats = self._latencies()
        if not lats:
            return 0.0
        idx = max(0, int(len(lats) * p / 100) - 1)
        return lats[idx]

    @property
    def mean(self) -> float:
        lats = self._latencies()
        return statistics.mean(lats) if lats else 0.0

    @property
    def p50(self) -> float:
        return self.percentile(50)

    @property
    def p95(self) -> float:
        return self.percentile(95)

    @property
    def p99(self) -> float:
        return self.percentile(99)

    @property
    def min_ms(self) -> float:
        lats = self._latencies()
        return min(lats) if lats else 0.0

    @property
    def max_ms(self) -> float:
        lats = self._latencies()
        return max(lats) if lats else 0.0


# ---------------------------------------------------------------------------
# Single HTTP call
# ---------------------------------------------------------------------------

async def call(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    json_body=None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = 30.0,
) -> RequestResult:
    url = f"{base_url}{path}"
    start = time.perf_counter()
    try:
        if method == "GET":
            resp = await client.get(url, timeout=timeout)
        else:
            resp = await client.post(url, json=json_body, timeout=timeout)
        latency_ms = (time.perf_counter() - start) * 1000
        return RequestResult(
            endpoint=path,
            method=method,
            status_code=resp.status_code,
            latency_ms=latency_ms,
        )
    except httpx.TimeoutException:
        latency_ms = (time.perf_counter() - start) * 1000
        return RequestResult(endpoint=path, method=method, status_code=0,
                             latency_ms=latency_ms, error="timeout")
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        return RequestResult(endpoint=path, method=method, status_code=0,
                             latency_ms=latency_ms, error=str(exc)[:80])


# ---------------------------------------------------------------------------
# Worker types
# ---------------------------------------------------------------------------

async def read_worker(
    user_id: int,
    deadline: float,
    stats: dict,
    lock: asyncio.Lock,
    base_url: str,
):
    """Hammers read-only endpoints concurrently."""
    limits = httpx.Limits(max_connections=5, max_keepalive_connections=3)
    async with httpx.AsyncClient(limits=limits) as client:
        while time.monotonic() < deadline:
            # Fire all read calls concurrently
            results = await asyncio.gather(
                call(client, "GET", "/health",      base_url=base_url, timeout=5.0),
                call(client, "GET", "/metrics",     base_url=base_url, timeout=10.0),
                call(client, "GET", "/audit-log",   base_url=base_url, timeout=10.0),
            )
            async with lock:
                for r in results:
                    stats[r.endpoint].add(r)
            await asyncio.sleep(0.1)


async def write_worker(
    user_id: int,
    deadline: float,
    stats: dict,
    lock: asyncio.Lock,
    pr_cycle: itertools.cycle,
    ss_cycle: itertools.cycle,
    base_url: str,
):
    """Fires write requests that trigger the multi-agent pipeline."""
    limits = httpx.Limits(max_connections=3, max_keepalive_connections=2)
    async with httpx.AsyncClient(limits=limits) as client:
        while time.monotonic() < deadline:
            # Fire both write endpoints concurrently
            pr_body = next(pr_cycle)
            ss_body = next(ss_cycle)
            results = await asyncio.gather(
                call(client, "POST", "/procurement/request",
                     pr_body, base_url=base_url, timeout=30.0),
                call(client, "POST", "/procurement/supplier/score",
                     ss_body, base_url=base_url, timeout=30.0),
            )
            async with lock:
                for r in results:
                    stats[r.endpoint].add(r)
            # brief pause between pipeline submissions
            await asyncio.sleep(0.5 + (user_id % 3) * 0.1)


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

async def run_benchmark(num_users: int, duration_s: int, base_url: str):
    # Pre-flight
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{base_url}/health", timeout=5.0)
            r.raise_for_status()
    except Exception as exc:
        print(f"\nFAIL Backend not reachable at {base_url}: {exc}")
        print("  Start first:  python -m uvicorn backend.main:app --port 8000\n")
        return

    endpoints = [
        "/health", "/metrics", "/audit-log",
        "/procurement/request", "/procurement/supplier/score",
    ]
    stats: dict[str, EndpointStats] = {ep: EndpointStats(endpoint=ep) for ep in endpoints}
    lock = asyncio.Lock()

    pr_cycle = itertools.cycle(PURCHASE_REQUESTS)
    ss_cycle = itertools.cycle(SUPPLIER_SCORE_REQUESTS)

    # Split users: 60% read workers, 40% write workers
    n_read  = max(1, int(num_users * 0.6))
    n_write = max(1, num_users - n_read)
    deadline = time.monotonic() + duration_s

    print(f"\n{'='*64}")
    print(f"  Procurement Intelligence Agent  --  API Benchmark")
    print(f"{'='*64}")
    print(f"  Target   : {base_url}")
    print(f"  Users    : {num_users} concurrent  ({n_read} read / {n_write} write)")
    print(f"  Duration : {duration_s}s")
    print(f"  Started  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*64}")
    print("  Running ...", end="", flush=True)

    wall_start = time.monotonic()

    tasks = (
        [asyncio.create_task(read_worker(i, deadline, stats, lock, base_url))
         for i in range(n_read)]
        +
        [asyncio.create_task(write_worker(i, deadline, stats, lock, pr_cycle, ss_cycle, base_url))
         for i in range(n_write)]
    )
    await asyncio.gather(*tasks)

    wall_elapsed = time.monotonic() - wall_start
    print(f"\r  Completed in {wall_elapsed:.1f}s          \n")

    # ---- report ----
    total_reqs = sum(s.total for s in stats.values())
    total_ok   = sum(s.successes for s in stats.values())
    rps = total_reqs / wall_elapsed if wall_elapsed else 0

    print(f"{'='*64}")
    print(f"  SUMMARY")
    print(f"{'='*64}")
    print(f"  Total requests : {total_reqs}")
    print(f"  Successful     : {total_ok}  ({total_ok/total_reqs*100:.1f}%)" if total_reqs else "  No requests completed")
    print(f"  Failed         : {total_reqs - total_ok}")
    print(f"  Throughput     : {rps:.1f} req/s")

    hdr = "{:<40} {:>5} {:>8} {:>7} {:>7} {:>7} {:>6}"
    row = "{:<40} {:>5} {:>8.1f} {:>7.1f} {:>7.1f} {:>7.1f} {:>6.1f}"
    print(f"\n{'-'*64}")
    print(hdr.format("Endpoint", "N", "Mean ms", "p50", "p95", "p99", "OK%"))
    print(f"{'-'*64}")

    for ep, s in stats.items():
        if s.total == 0:
            continue
        print(row.format(ep[:40], s.total, s.mean, s.p50, s.p95, s.p99, s.success_rate))

    print(f"{'-'*64}")

    # Sub-300ms verdict
    targets = [
        ("POST /procurement/request",        stats["/procurement/request"]),
        ("POST /procurement/supplier/score", stats["/procurement/supplier/score"]),
    ]
    print("\n  Sub-300ms verdict (multi-agent pipeline endpoints):")
    for label, s in targets:
        if s.total == 0:
            print(f"    --  {label}: no data")
            continue
        verdict = "PASS" if s.p95 < 300 else "FAIL"
        print(f"    {verdict}  {label}  |  "
              f"p50={s.p50:.0f}ms  p95={s.p95:.0f}ms  p99={s.p99:.0f}ms  "
              f"({s.successes}/{s.total} ok)")

    print(f"\n{'='*64}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Procurement Agent API benchmark")
    parser.add_argument("--users",    type=int, default=20,
                        help="Concurrent users (default 20)")
    parser.add_argument("--duration", type=int, default=60,
                        help="Test duration in seconds (default 60)")
    parser.add_argument("--endpoint", type=str, default=DEFAULT_BASE_URL,
                        help="Base URL of the API")
    args = parser.parse_args()
    asyncio.run(run_benchmark(args.users, args.duration, base_url=args.endpoint))
