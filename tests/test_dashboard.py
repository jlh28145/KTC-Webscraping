"""Streamlit dashboard tests: the real script, run headless, with the API stubbed."""

from pathlib import Path

import pytest
import requests
from streamlit.testing.v1 import AppTest

DASHBOARD = str(Path(__file__).resolve().parents[1] / "dashboard" / "dashboard.py")

RANKINGS = [
    {"player_name": "Jahmyr Gibbs", "position": "RB", "rank_overall": 1, "value": 9999.0},
    {"player_name": "Josh Allen", "position": "QB", "rank_overall": 2, "value": 9995.0},
]
HISTORY = [
    {"player_name": "Jahmyr Gibbs", "scrape_date": "2026-10-19", "rank_overall": 1},
    {"player_name": "Jahmyr Gibbs", "scrape_date": "2026-10-18", "rank_overall": 2},
]


class _Response:
    def __init__(self, status_code: int, payload) -> None:
        self.status_code = status_code
        self._payload = payload
        self.content = b"x"
        self.text = str(payload)

    def json(self):
        return self._payload


@pytest.fixture
def api(monkeypatch):
    """Stub requests.get with canned API responses and record every call."""

    calls: list[tuple[str, dict | None]] = []
    responses = {
        "/scrape-dates": _Response(200, ["2026-10-19", "2026-10-18"]),
        "/rankings": _Response(200, RANKINGS),
        "/player": _Response(200, HISTORY),
    }

    def fake_get(url: str, params=None, timeout=None):
        assert timeout is not None, "every dashboard request must set a timeout"
        path = url.removeprefix("http://api.test")
        calls.append((path, params))
        return responses[path]

    monkeypatch.setenv("KTC_API_URL", "http://api.test")
    monkeypatch.setattr(requests, "get", fake_get)
    return {"calls": calls, "responses": responses}


def _run() -> AppTest:
    return AppTest.from_file(DASHBOARD, default_timeout=30).run()


def test_dashboard_renders_the_latest_snapshot(api) -> None:
    app = _run()

    assert not app.exception
    assert not app.error
    assert app.sidebar.selectbox[0].options == ["2026-10-19", "2026-10-18"]
    assert [header.value for header in app.subheader] == ["📊 Player Rankings (2026-10-19)"]
    assert ("/rankings", {"page": 1, "limit": 25, "scrape_date": "2026-10-19"}) in api["calls"]


def test_dashboard_passes_filters_to_the_api(api) -> None:
    app = _run()

    app.sidebar.selectbox[0].select("2026-10-18")
    app.sidebar.selectbox[1].select("PICK")
    app.sidebar.text_input[0].input("KCC")
    app.run()

    assert api["calls"][-1] == (
        "/rankings",
        {"page": 1, "limit": 25, "scrape_date": "2026-10-18", "position": "PICK", "team": "KCC"},
    )


def test_dashboard_search_shows_player_history(api) -> None:
    app = _run()

    app.text_input[0].input("gibbs").run()

    assert "Ranking history for 'gibbs'" in [header.value for header in app.subheader]
    assert ("/player", {"name": "gibbs"}) in api["calls"]


def test_dashboard_reports_an_unreachable_api(monkeypatch) -> None:
    def refuse(url, params=None, timeout=None):
        raise requests.ConnectionError("connection refused")

    monkeypatch.setenv("KTC_API_URL", "http://api.test")
    monkeypatch.setattr(requests, "get", refuse)

    app = _run()

    assert not app.exception
    assert len(app.error) == 1
    assert app.error[0].value.startswith("Could not reach the API at http://api.test")


def test_dashboard_reports_api_errors(api) -> None:
    api["responses"]["/scrape-dates"] = _Response(503, {"detail": "Run the scraper first."})

    app = _run()

    assert not app.exception
    assert [error.value for error in app.error] == ["API error 503: Run the scraper first."]
