"""H2-2 trajectory scoring: sequence modes, args, forbidden calls, terminal state."""
import pytest

from evaluation.agent_trace_eval import (forbidden_call, score_trajectory,
                                         terminal_state_match, trajectory_match)


def test_trajectory_modes():
    assert trajectory_match(["a", "b"], ["a", "x", "b"], "partial")
    assert not trajectory_match(["a", "b"], ["a", "x", "b"], "ordered")
    assert trajectory_match(["a", "b"], ["b", "a"], "unordered")
    assert not trajectory_match(["a", "b"], ["a"], "partial")
    with pytest.raises(ValueError):
        trajectory_match(["a"], ["a"], "unknown")


def test_forbidden_and_terminal_state():
    assert forbidden_call(["request_refund"], ["get_order", "request_refund"])
    assert not forbidden_call(["request_refund"], ["get_order"])
    assert terminal_state_match({"executor_calls": 0}, {"executor_calls": 0, "handoff_count": 0})
    assert not terminal_state_match({"executor_calls": 1}, {"executor_calls": 0})


def test_score_trajectory_combines_checks():
    traces = [
        {"tool_name": "get_order", "validated_input": {"order_id": "ORD-1001"}},
        {"tool_name": "get_order", "validated_input": {"order_id": "ORD-1001"},
         "error_code": "timeout"},
    ]
    expected = {
        "tools": ["get_order", "get_order"],
        "tool_mode": "ordered",
        "key_args": {"get_order": {"order_id": "ORD-1001"}},
        "forbidden_tools": ["request_refund"],
        "error_codes": ["timeout"],
        "terminal_state": {"executor_calls": 0},
    }
    checks = score_trajectory(traces, expected, {"executor_calls": 0})
    assert all(checks.values()), checks
    assert checks["trajectory"] and checks["forbidden_tools"]
    assert checks["key_args:get_order"] and checks["error_codes"]
