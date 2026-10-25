"""H2-2 runner: replay/fault cases and pass metrics summary."""
import json
from pathlib import Path

from evaluation.prepare_online_eval import prepare
from evaluation.run_harness_eval import NOW, _load_cases, main, run_case, summarize

CASES = Path(__file__).resolve().parents[1] / "evaluation/cases/h2_2_cases.json"


def test_replay_case_runs_without_model_calls():
    case = next(c for c in _load_cases(CASES) if c["id"] == "replay_order")
    result = run_case(case, 1, prepare(NOW)[0])
    assert result["passed"], result["checks"]
    assert result["tools_used"] == ["get_order"]
    assert result["terminal_state"]["order_status"] == "shipped"
    assert result["fault_events"] == []


def test_fault_case_records_injected_event():
    case = next(c for c in _load_cases(CASES) if c["id"] == "fault_not_found")
    result = run_case(case, 1, prepare(NOW)[0])
    assert result["passed"], result["checks"]
    assert result["fault_events"][0]["kind"] == "not_found"
    assert any(trace.get("error_code") == "not_found" for trace in result["tool_traces"])


def test_runner_main_writes_json_and_markdown(tmp_path):
    output = tmp_path / "h2_2.json"
    code = main(["--cases", str(CASES), "--output", str(output)])
    assert code == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["pass_metrics"]["cases"]
    assert report["pass_metrics"]["pass@runs"]["numerator"] >= 1
    assert output.with_suffix(".md").exists()
