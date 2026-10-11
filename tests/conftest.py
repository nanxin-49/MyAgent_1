import pytest
from api import main
from tests.auth_helpers import install_http_auth


@pytest.fixture
def authenticated_http(monkeypatch):
    """Opt-in legacy HTTP tests use fixed server-owned credentials, never body identity."""
    install_http_auth(monkeypatch, main.app)
