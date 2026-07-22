"""Run the repository's representative Agent cases against a live API."""

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path

import httpx

CASES_PATH = Path(__file__).resolve().parents[1] / "evals" / "travel_cases.json"


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--token")
    arguments = parser.parse_args()
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    headers = {"Authorization": f"Bearer {arguments.token}"} if arguments.token else {}
    rows = []
    async with httpx.AsyncClient(
        base_url=arguments.base_url,
        headers=headers,
        timeout=120,
    ) as client:
        for case in cases:
            started = time.perf_counter()
            try:
                response = await client.post(
                    "/chat",
                    json={
                        "message": case["prompt"],
                        "thread_id": f"eval-{case['id']}",
                        "channel": "eval",
                    },
                )
                payload = response.json()
                passed = response.is_success and bool(payload.get("message"))
                error = None if passed else payload
            except Exception as exception:
                passed = False
                error = f"{type(exception).__name__}: {exception}"
            rows.append(
                {
                    "id": case["id"],
                    "passed": passed,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                    "error": error,
                }
            )
    latencies = [row["latency_ms"] for row in rows]
    report = {
        "cases": len(rows),
        "passed": sum(row["passed"] for row in rows),
        "success_rate": round(sum(row["passed"] for row in rows) / len(rows), 3),
        "p50_latency_ms": round(statistics.median(latencies), 2),
        "results": rows,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
