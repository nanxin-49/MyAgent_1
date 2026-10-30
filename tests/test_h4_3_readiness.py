"""H4-3: liveness and dependency readiness are separate and model-free."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from fastapi.testclient import TestClient

from api import main
from tests.test_memory_boundary import RedisStore, manager


class FakeMemory:
    def __init__(self, checks):
        self.checks = checks
        self.readiness_calls = 0

    async def readiness(self):
        self.readiness_calls += 1
        return self.checks


class PingStore(RedisStore):
    def __init__(self, ok):
        super().__init__()
        self.ok = ok

    async def ping(self):
        return self.ok


class Chroma:
    def __init__(self, ok):
        self.ok = ok

    def heartbeat(self):
        return self.ok


def orchestrator():
    return SimpleNamespace(get_stats=lambda: {"agents": {}})


def test_health_is_liveness_and_does_not_probe_dependencies(monkeypatch):
    memory = FakeMemory({"redis": False, "chroma": False})
    monkeypatch.setattr(main, "_memory", memory)
    monkeypatch.setattr(main, "_orchestrator", orchestrator())
    response = TestClient(main.app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert memory.readiness_calls == 0


def test_ready_returns_200_only_when_all_dependencies_are_ready(monkeypatch):
    monkeypatch.setattr(main, "_memory", FakeMemory({"redis": True, "chroma": True}))
    monkeypatch.setattr(main, "_orchestrator", orchestrator())
    response = TestClient(main.app).get("/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"orchestrator": True, "redis": True, "chroma": True},
    }


def test_ready_returns_503_without_leaking_exception_text(monkeypatch):
    monkeypatch.setattr(main, "_memory", FakeMemory({"redis": True, "chroma": False}))
    monkeypatch.setattr(main, "_orchestrator", orchestrator())
    response = TestClient(main.app).get("/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"orchestrator": True, "redis": True, "chroma": False},
    }


def test_ready_without_memory_or_orchestrator_is_not_ready(monkeypatch):
    monkeypatch.setattr(main, "_memory", None)
    monkeypatch.setattr(main, "_orchestrator", None)
    response = TestClient(main.app).get("/ready")
    assert response.status_code == 503
    assert response.json()["checks"] == {
        "orchestrator": False, "redis": False, "chroma": False}


def test_ready_does_not_leak_readiness_exception(monkeypatch):
    class BrokenMemory:
        async def readiness(self):
            raise RuntimeError("redis password should not leak")

    monkeypatch.setattr(main, "_memory", BrokenMemory())
    monkeypatch.setattr(main, "_orchestrator", orchestrator())
    response = TestClient(main.app).get("/ready")
    assert response.status_code == 503
    assert response.json()["checks"] == {
        "orchestrator": True, "redis": False, "chroma": False}
    assert "password" not in response.text


def test_memory_readiness_checks_redis_and_chroma():
    async def scenario():
        memory = manager()
        memory._redis = PingStore(True)
        memory._chroma = Chroma(True)
        assert await memory.readiness() == {"redis": True, "chroma": True}
        memory._redis = PingStore(False)
        memory._chroma = Chroma(False)
        assert await memory.readiness() == {"redis": False, "chroma": False}

    asyncio.run(scenario())
