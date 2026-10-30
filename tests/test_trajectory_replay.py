"""H2-2 trajectory recording, conversion, and replay."""
import asyncio
import json
from pathlib import Path

from evaluation.scripted_model import ScriptedModel, from_trajectory
from evaluation.trajectory import (SCHEMA, TrajectoryRecorder, from_model_ledger,
                                   load, turns_for_replay)

ROOT = Path(__file__).resolve().parents[1]


def test_recorder_captures_response_and_request_hashes(tmp_path):
    inner = ScriptedModel([
        {"content": [{"type": "text", "text": "先查订单"},
                     {"type": "tool_use", "id": "call_1", "name": "get_order",
                      "input": {"order_id": "ORD-1001"}}],
         "stop_reason": "tool_use",
         "usage": {"input_tokens": 10, "output_tokens": 5,
                   "cache_read_input_tokens": 2}},
        {"content": [{"type": "text", "text": "完成"}], "stop_reason": "end_turn"},
    ])
    recorder = TrajectoryRecorder(inner, "support", case_id="recorded")
    asyncio.run(recorder.create(model="m", system="sys",
                                messages=[{"role": "user", "content": "查订单"}],
                                tools=[{"name": "get_order"}]))
    asyncio.run(recorder.create(model="m", system="sys",
                                messages=[{"role": "user", "content": [
                                    {"type": "tool_result", "tool_use_id": "call_1",
                                     "content": "{\"success\": true}"}]}]))
    assert len(recorder.turns) == 2
    first = recorder.turns[0]
    assert first["request"]["messages_sha256"]
    assert first["response"]["stop_reason"] == "tool_use"
    assert first["response"]["content"][1]["name"] == "get_order"
    assert first["response"]["usage"]["cache_read_input_tokens"] == 2
    assert recorder.turns[1]["request"]["tool_results_sent"][0]["tool_use_id"] == "call_1"

    path = tmp_path / "trajectory.json"
    recorder.dump(path, case={"id": "recorded", "message": "查订单", "turn_range": []})
    loaded = load(path)
    assert loaded["schema"] == SCHEMA and loaded["version"] == 1
    assert len(turns_for_replay(loaded)) == 2


def test_h1_1_ledger_conversion_keeps_support_turns():
    ledger = json.loads((ROOT / "evaluation/reports/H1-1/20261025T091107Z-repair1/model_ledger.json")
                        .read_text(encoding="utf-8"))
    trajectory = from_model_ledger(ledger, case_id="h1_1_s1b", turn_range=[1, 3],
                                   stages={"support"})
    assert trajectory["evidence_level"] == "converted_h1_1_ledger"
    assert [turn["stage"] for turn in trajectory["turns"]] == ["support", "support"]
    assert trajectory["turns"][0]["response"]["content"][0]["type"] == "text"
    assert trajectory["turns"][0]["request"]["messages_sha256"] is None


def test_replay_model_preserves_canonical_content_and_asserts_consumption():
    model = from_trajectory(ROOT / "evaluation/trajectories/replay_order.json")
    first = asyncio.run(model.create(model="scripted", messages=[]))
    assert first.content[0].type == "tool_use"
    assert first.content[0].name == "get_order"
    second = asyncio.run(model.create(model="scripted", messages=[]))
    assert second.stop_reason == "end_turn"
    model.assert_consumed()
    assert model.calls
