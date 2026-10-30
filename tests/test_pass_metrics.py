"""H2-2 pass@runs / pass^runs aggregation (runs is not retrieval depth k)."""
from evaluation.system_eval import SystemEvalCase, evaluate_system, pass_metrics


def case(case_id, run, passed):
    return SystemEvalCase(case_id, "tool", {}, {"checks": {"ok": passed}, "passed": passed},
                          mode="harness_eval", run=run)


def test_pass_metrics_any_and_all():
    report = pass_metrics([case("two_of_three", run, run != 3) for run in (1, 2, 3)])
    row = report["cases"][0]
    assert row == {"case_id": "two_of_three", "runs": 3, "passes": 2,
                   "pass@runs": True, "pass^runs": False}
    assert report["pass@runs"]["numerator"] == 1
    assert report["pass^runs"]["numerator"] == 0

    all_pass = pass_metrics([case("all", run, True) for run in (1, 2, 3)])
    assert all_pass["pass^runs"]["numerator"] == 1


def test_single_run_is_reported_and_unmeasured_without_run():
    report = pass_metrics([case("single", 1, True)])
    assert report["cases"][0]["runs"] == 1
    empty = pass_metrics([SystemEvalCase("no_run", "tool", {}, {"checks": {"x": True}})])
    assert empty["cases"] == []
    assert empty["pass@runs"]["value"] is None


def test_evaluate_system_includes_pass_metrics():
    report = evaluate_system([case("c", 1, True), case("c", 2, False)])
    assert report["pass_metrics"]["cases"][0]["runs"] == 2
    assert report["pass_metrics"]["pass^runs"]["numerator"] == 0
