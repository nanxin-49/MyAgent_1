"""H5-2: environment compatibility and CartCare deployment naming."""
from __future__ import annotations

from pathlib import Path

import yaml

from agents.agent_orchestrator import _env_int
from core.env import compat_env, compat_env_float, compat_env_int

ROOT = Path(__file__).resolve().parents[1]


def test_compat_env_prefers_cartcare_and_falls_back_to_echomind(monkeypatch):
    monkeypatch.setenv("CARTCARE_SKILLS_DIR", "/new")
    monkeypatch.setenv("ECHOMIND_SKILLS_DIR", "/old")
    assert compat_env("CARTCARE_SKILLS_DIR", "ECHOMIND_SKILLS_DIR") == "/new"
    monkeypatch.delenv("CARTCARE_SKILLS_DIR")
    assert compat_env("CARTCARE_SKILLS_DIR", "ECHOMIND_SKILLS_DIR") == "/old"
    monkeypatch.delenv("ECHOMIND_SKILLS_DIR")
    assert compat_env("CARTCARE_SKILLS_DIR", "ECHOMIND_SKILLS_DIR", "default") == "default"


def test_compat_numeric_helpers(monkeypatch):
    monkeypatch.setenv("CARTCARE_TOOL_TRACE_MAX", "111")
    monkeypatch.setenv("ECHOMIND_TOOL_TRACE_MAX", "222")
    assert compat_env_int("CARTCARE_TOOL_TRACE_MAX", "ECHOMIND_TOOL_TRACE_MAX", 200) == 111
    monkeypatch.delenv("CARTCARE_TOOL_TRACE_MAX")
    assert compat_env_int("CARTCARE_TOOL_TRACE_MAX", "ECHOMIND_TOOL_TRACE_MAX", 200) == 222
    monkeypatch.setenv("CARTCARE_COMPOSER_TEMPERATURE", "0.7")
    assert compat_env_float("CARTCARE_COMPOSER_TEMPERATURE",
                            "ECHOMIND_COMPOSER_TEMPERATURE", 0.1) == 0.7


def test_legacy_agent_env_helper_supports_fallback(monkeypatch):
    monkeypatch.setenv("CARTCARE_TOOL_TRACE_MAX", "123")
    monkeypatch.setenv("ECHOMIND_TOOL_TRACE_MAX", "456")
    assert _env_int("CARTCARE_TOOL_TRACE_MAX", 200, "ECHOMIND_TOOL_TRACE_MAX") == 123
    monkeypatch.delenv("CARTCARE_TOOL_TRACE_MAX")
    assert _env_int("CARTCARE_TOOL_TRACE_MAX", 200, "ECHOMIND_TOOL_TRACE_MAX") == 456


def test_compose_uses_cartcare_services_containers_and_network():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert "cartcare" in services
    assert "echomind" not in services
    assert services["redis"]["container_name"] == "cartcare-redis"
    assert services["chromadb"]["container_name"] == "cartcare-chromadb"
    assert services["prometheus"]["container_name"] == "cartcare-prometheus"
    assert services["cartcare"]["container_name"] == "cartcare-app"
    assert services["nginx"]["container_name"] == "cartcare-nginx"
    assert "cartcare-network" in compose["networks"]
    assert "echomind-network" not in compose["networks"]
    assert services["nginx"]["depends_on"]["cartcare"]["condition"] == "service_healthy"
    assert "CARTCARE_SKILLS_DIR=/app/skills" in services["cartcare"]["environment"]


def test_nginx_and_prometheus_target_cartcare():
    nginx = (ROOT / "config/nginx/nginx.conf").read_text(encoding="utf-8")
    prometheus = (ROOT / "config/prometheus.yml").read_text(encoding="utf-8")
    assert "server cartcare:8000" in nginx
    assert "server echomind:8000" not in nginx
    assert "upstream cartcare_backend" in nginx
    assert "targets: ['cartcare:8000']" in prometheus
    assert "job_name: 'cartcare-app'" in prometheus
    assert "targets: ['echomind:8000']" not in prometheus


def test_deploy_scripts_and_env_example_use_cartcare_names():
    run_image = (ROOT / "run-image.sh").read_text(encoding="utf-8")
    deploy = (ROOT / "docker-deploy.sh").read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert 'IMAGE_NAME="cartcare"' in run_image
    assert 'CONTAINER_NAME="cartcare-app"' in run_image
    assert "docker cp cartcare-redis:" in deploy
    assert "docker cp cartcare-chromadb:" in deploy
    assert "./docker-deploy.sh logs cartcare" in deploy
    assert "REDIS_PASSWORD=cartcare123" in env_example
    assert "CARTCARE_SKILLS_DIR" in (ROOT / "skills/README.md").read_text(encoding="utf-8")


def test_readme_links_the_sunk_documents():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for path in ("docs/architecture.md", "docs/evaluation.md", "docs/operations.md",
                 "docs/limitations.md", "docs/naming.md"):
        assert path in readme
        assert (ROOT / path).is_file()
    assert "cash/" not in readme
    assert "以下为 Windows PowerShell" not in readme
