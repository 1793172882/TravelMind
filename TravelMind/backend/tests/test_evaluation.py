import json
from pathlib import Path

from scripts.evaluate import CATEGORY_RULES, score_case


def test_evaluation_dataset_and_scoring() -> None:
    path = Path(__file__).resolve().parents[1] / "evals" / "travel_cases.json"
    cases = json.loads(path.read_text(encoding="utf-8"))

    assert len(cases) == 100
    assert len({case["id"] for case in cases}) == 100
    assert all(case["category"] in CATEGORY_RULES or case["category"] == "composite" for case in cases)

    case = {
        "id": "example",
        "category": "composite",
        "expected_tools": ["amap.weather"],
        "forbidden_tools": ["trip.create"],
        "required_terms": [["真实", "实时"]],
        "expected_status": "completed",
    }
    result = score_case(
        case,
        {"message": "这是实时天气。", "status": "completed"},
        [{"type": "tool.started", "data": {"tool": "amap.weather"}}],
        True,
    )

    assert result["passed"]
