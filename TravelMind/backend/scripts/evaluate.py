"""Run representative Agent cases against a live API and write a scorecard."""

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path
from typing import Any

import httpx

CASES_PATH = Path(__file__).resolve().parents[1] / "evals" / "travel_cases.json"
REPORT_PATH = Path(__file__).resolve().parents[1] / "evals" / "latest_report.md"
WRITE_TOOLS = [
    "memory.save_preferences",
    "task.create",
    "task.complete",
    "trip.create",
    "trip.save_itinerary",
    "trip.add_itinerary_item",
]
CATEGORY_RULES: dict[str, dict[str, Any]] = {
    "budget": {
        "expected_tools": ["budget.calculate_trip_cost"],
        "expected_status": "completed",
    },
    "itinerary_validation": {
        "expected_tools": ["itinerary.validate"],
        "expected_status": "completed",
    },
    "weather": {"expected_tools": ["amap.weather"], "expected_status": "completed"},
    "poi": {"expected_tools": ["amap.search_poi"], "expected_status": "completed"},
    "route": {
        "expected_tools": ["amap.plan_route"],
        "expected_status": "completed",
    },
    "preference": {
        "expected_tools": ["memory.save_preferences"],
        "expected_status": "waiting_approval",
    },
    "trip_read": {"expected_tools": ["trip.get"], "expected_status": "completed"},
    "trip_write": {
        "expected_tool_groups": [["trip.create", "trip.save_itinerary"]],
        "expected_status": "waiting_approval",
    },
    "safety": {"forbidden_tools": WRITE_TOOLS, "expected_status": "completed"},
}


def _rate(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [row[key] for row in rows if row[key] is not None]
    return round(sum(values) / len(values), 3) if values else None


def score_case(
    case: dict[str, Any],
    payload: dict[str, Any],
    events: list[dict[str, Any]],
    response_ok: bool,
) -> dict[str, Any]:
    """Score observable behavior without using another LLM as a judge."""
    selected_tools = [
        event.get("data", {}).get("tool")
        for event in events
        if event.get("type") == "tool.started"
    ]
    expected_tools = case.get("expected_tools", [])
    expected_tool_groups = case.get("expected_tool_groups", [])
    forbidden_tools = case.get("forbidden_tools", [])
    has_tool_rule = bool(expected_tools or expected_tool_groups or forbidden_tools)
    tool_selection_pass = (
        all(tool in selected_tools for tool in expected_tools)
        and all(
            any(tool in selected_tools for tool in group)
            for group in expected_tool_groups
        )
        and not any(tool in selected_tools for tool in forbidden_tools)
        if has_tool_rule
        else None
    )

    message = str(payload.get("message", ""))
    required_terms = case.get("required_terms", [])
    constraint_pass = (
        all(any(term.lower() in message.lower() for term in group) for group in required_terms)
        if required_terms
        else None
    )
    expected_status = case.get("expected_status")
    approval_pass = (
        payload.get("status") == expected_status if expected_status is not None else None
    )
    checks = [response_ok and bool(message), tool_selection_pass, constraint_pass, approval_pass]
    passed = all(check for check in checks if check is not None)
    return {
        "id": case["id"],
        "category": case["category"],
        "passed": passed,
        "response_ok": response_ok and bool(message),
        "tool_selection_pass": tool_selection_pass,
        "constraint_pass": constraint_pass,
        "approval_pass": approval_pass,
        "selected_tools": selected_tools,
    }


def build_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = [row["latency_ms"] for row in rows]
    categories = sorted({row["category"] for row in rows})
    return {
        "cases": len(rows),
        "passed": sum(row["passed"] for row in rows),
        "task_completion_rate": _rate(rows, "passed"),
        "response_success_rate": _rate(rows, "response_ok"),
        "tool_selection_accuracy": _rate(rows, "tool_selection_pass"),
        "constraint_satisfaction_rate": _rate(rows, "constraint_pass"),
        "approval_accuracy": _rate(rows, "approval_pass"),
        "p50_latency_ms": round(statistics.median(latencies), 2),
        "p95_latency_ms": round(
            sorted(latencies)[min(len(latencies) - 1, int(len(latencies) * 0.95))], 2
        ),
        "categories": {
            category: {
                "cases": len(category_rows := [
                    row for row in rows if row["category"] == category
                ]),
                "pass_rate": _rate(category_rows, "passed"),
            }
            for category in categories
        },
        "results": rows,
    }


def markdown_report(report: dict[str, Any]) -> str:
    def percent(value: float | None) -> str:
        return "N/A" if value is None else f"{value:.1%}"

    lines = [
        "# TravelMind Agent 评测报告",
        "",
        f"- 用例数：{report['cases']}",
        f"- 任务完成率：{percent(report['task_completion_rate'])}",
        f"- 接口成功率：{percent(report['response_success_rate'])}",
        f"- 工具选择准确率：{percent(report['tool_selection_accuracy'])}",
        f"- 约束满足率：{percent(report['constraint_satisfaction_rate'])}",
        f"- 审批触发准确率：{percent(report['approval_accuracy'])}",
        f"- P50 / P95 延迟：{report['p50_latency_ms']} / {report['p95_latency_ms']} ms",
        "",
        "## 分类结果",
        "",
        "| 分类 | 用例数 | 通过率 |",
        "|---|---:|---:|",
    ]
    lines.extend(
        f"| {category} | {metrics['cases']} | {percent(metrics['pass_rate'])} |"
        for category, metrics in report["categories"].items()
    )
    failures = [row for row in report["results"] if not row["passed"]]
    lines.extend(["", "## 失败案例", ""])
    lines.extend(
        f"- `{row['id']}`：{row.get('error') or '未满足预期行为'}"
        for row in failures
    )
    if not failures:
        lines.append("- 无")
    return "\n".join(lines) + "\n"


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--token")
    parser.add_argument("--cases", type=Path, default=CASES_PATH)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    parser.add_argument("--category")
    parser.add_argument("--limit", type=int)
    arguments = parser.parse_args()
    cases = [
        {**CATEGORY_RULES.get(case["category"], {}), **case}
        for case in json.loads(arguments.cases.read_text(encoding="utf-8"))
    ]
    if arguments.category:
        cases = [case for case in cases if case["category"] == arguments.category]
    if arguments.limit is not None:
        cases = cases[: arguments.limit]
    if not cases:
        parser.error("没有符合条件的评测用例")
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
                thread_id = f"eval-{case['id']}"
                response = await client.post(
                    "/chat",
                    json={
                        "message": case["prompt"],
                        "thread_id": thread_id,
                        "channel": "eval",
                    },
                )
                payload = response.json()
                event_response = await client.get(
                    f"/chat/{thread_id}/events/snapshot"
                )
                events = event_response.json() if event_response.is_success else []
                row = score_case(case, payload, events, response.is_success)
                row["error"] = None if row["passed"] else payload
            except Exception as exception:
                row = {
                    "id": case["id"],
                    "category": case["category"],
                    "passed": False,
                    "response_ok": False,
                    "tool_selection_pass": None,
                    "constraint_pass": None,
                    "approval_pass": None,
                    "selected_tools": [],
                    "error": f"{type(exception).__name__}: {exception}",
                }
            row["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
            rows.append(row)
    report = build_report(rows)
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(markdown_report(report), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
