import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from ktc_webscraping.load import create_connection, insert_player_data
from ktc_webscraping.models import PlayerRecord


def _record(
    scrape_date: str,
    name: str,
    position: str,
    rank: int | None,
    team: str | None,
    tier: int,
    value: float,
) -> PlayerRecord:
    return PlayerRecord(
        scrape_date=scrape_date,
        player_name=name,
        position=position,
        rank_overall=rank,
        rank_position=None if position == "PICK" else 1,
        team=team,
        source="keeptradecut",
        age=None if position == "PICK" else 25.0,
        tier=tier,
        value=value,
        scraped_at=f"{scrape_date}T13:00:00+00:00",
    )


POSTGRES_URL = os.getenv("KTC_TEST_POSTGRES_URL")


def _drop_postgres_rankings() -> None:
    import psycopg

    with psycopg.connect(POSTGRES_URL, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS ktc_rankings")


@pytest.fixture(
    params=[
        "sqlite",
        pytest.param(
            "postgres",
            marks=pytest.mark.skipif(
                not POSTGRES_URL, reason="set KTC_TEST_POSTGRES_URL to run the API on Postgres"
            ),
        ),
    ]
)
def backend(request) -> str:
    return request.param


@pytest.fixture
def seeded_db(backend: str, monkeypatch, tmp_path: Path):
    """Two snapshots: Gibbs moves from 2nd to 1st between 2026-10-18 and 2026-10-19.

    Every test using this fixture runs once per backend (SQLite, and Postgres
    when KTC_TEST_POSTGRES_URL is set), so the API is held to the same answers on both.
    """

    records = [
        _record("2026-10-18", "Josh Allen", "QB", 1, "BUF", 1, 9999.0),
        _record("2026-10-18", "Jahmyr Gibbs", "RB", 2, "DET", 1, 9990.0),
        _record("2026-10-19", "Jahmyr Gibbs", "RB", 1, "DET", 1, 9999.0),
        _record("2026-10-19", "Josh Allen", "QB", 2, "BUF", 1, 9995.0),
        _record("2026-10-19", "2027 Late 1st", "PICK", None, None, 4, 5000.0),
        _record("2026-10-19", "2027 Early 1st", "PICK", None, None, 3, 6871.0),
        _record("2026-10-19", "Travis Kelce", "TE", 3, "KCC", 2, 7000.0),
    ]
    if backend == "sqlite":
        db_path = tmp_path / "api.db"
        conn = create_connection(db_path)
        insert_player_data(conn, records)
        conn.close()
        monkeypatch.delenv("KTC_DATABASE_URL", raising=False)
        monkeypatch.setenv("KTC_DB_PATH", str(db_path))
        yield db_path
        return

    _drop_postgres_rankings()
    conn = create_connection(tmp_path / "unused.db", database_url=POSTGRES_URL)
    insert_player_data(conn, records)
    conn.close()
    monkeypatch.setenv("KTC_DATABASE_URL", POSTGRES_URL)
    yield None
    _drop_postgres_rankings()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _names(response) -> list[str]:
    return [row["player_name"] for row in response.json()]


def test_health_does_not_need_a_database(monkeypatch, tmp_path: Path, client) -> None:
    monkeypatch.setenv("KTC_DB_PATH", str(tmp_path / "missing.db"))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_rankings_defaults_to_latest_snapshot_with_picks_last(seeded_db, client) -> None:
    response = client.get("/rankings")

    assert response.status_code == 200
    assert {row["scrape_date"] for row in response.json()} == {"2026-10-19"}
    assert _names(response) == [
        "Jahmyr Gibbs",
        "Josh Allen",
        "Travis Kelce",
        "2027 Early 1st",
        "2027 Late 1st",
    ]


def test_rankings_returns_typed_rows(seeded_db, client) -> None:
    row = client.get("/rankings", params={"limit": 1}).json()[0]

    assert set(row) == {
        "id",
        "scrape_date",
        "player_name",
        "position",
        "rank_overall",
        "rank_position",
        "team",
        "source",
        "age",
        "tier",
        "value",
        "scraped_at",
        "ktc_player_id",
        "player_key",
    }
    assert row["rank_overall"] == 1
    assert row["value"] == 9999.0


def test_rankings_can_select_an_earlier_snapshot(seeded_db, client) -> None:
    response = client.get("/rankings", params={"scrape_date": "2026-10-18"})

    assert _names(response) == ["Josh Allen", "Jahmyr Gibbs"]


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"position": "pick"}, ["2027 Early 1st", "2027 Late 1st"]),
        ({"team": "kcc"}, ["Travis Kelce"]),
        ({"tier": 1}, ["Jahmyr Gibbs", "Josh Allen"]),
        ({"position": "RB", "team": "BUF"}, []),
    ],
)
def test_rankings_filters_are_case_insensitive_and_combine(
    seeded_db, client, params, expected
) -> None:
    assert _names(client.get("/rankings", params=params)) == expected


def test_rankings_paginates_in_rank_order(seeded_db, client) -> None:
    first = client.get("/rankings", params={"limit": 2, "page": 1})
    second = client.get("/rankings", params={"limit": 2, "page": 2})

    assert _names(first) == ["Jahmyr Gibbs", "Josh Allen"]
    assert _names(second) == ["Travis Kelce", "2027 Early 1st"]


@pytest.mark.parametrize(
    "params",
    [{"page": 0}, {"limit": 0}, {"limit": 101}, {"tier": 0}, {"tier": "one"}],
)
def test_rankings_rejects_invalid_query_params(seeded_db, client, params) -> None:
    assert client.get("/rankings", params=params).status_code == 422


def test_get_ranking_by_id(seeded_db, client) -> None:
    first = client.get("/rankings").json()[0]

    response = client.get(f"/rankings/{first['id']}")

    assert response.status_code == 200
    assert response.json() == first


def test_get_ranking_returns_404_for_unknown_id(seeded_db, client) -> None:
    response = client.get("/rankings/9999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Ranking 9999 not found"}


def test_player_history_spans_snapshots_newest_first(seeded_db, client) -> None:
    response = client.get("/player", params={"name": "GIBBS"})

    assert [(row["scrape_date"], row["rank_overall"]) for row in response.json()] == [
        ("2026-10-19", 1),
        ("2026-10-18", 2),
    ]


def test_player_search_treats_wildcards_literally(seeded_db, client) -> None:
    assert client.get("/player", params={"name": "%"}).json() == []
    assert client.get("/player", params={"name": "_"}).json() == []


def test_player_search_requires_a_name(seeded_db, client) -> None:
    assert client.get("/player").status_code == 422
    assert client.get("/player", params={"name": ""}).status_code == 422


def test_scrape_dates_lists_snapshots_newest_first(seeded_db, client) -> None:
    assert client.get("/scrape-dates").json() == ["2026-10-19", "2026-10-18"]


def test_missing_database_returns_503_without_creating_a_file(
    monkeypatch, tmp_path: Path, client
) -> None:
    db_path = tmp_path / "missing.db"
    monkeypatch.delenv("KTC_DATABASE_URL", raising=False)
    monkeypatch.setenv("KTC_DB_PATH", str(db_path))

    response = client.get("/rankings")

    assert response.status_code == 503
    assert "Run the scraper first" in response.json()["detail"]
    assert not db_path.exists()


def test_database_without_rankings_table_returns_503(monkeypatch, tmp_path: Path, client) -> None:
    db_path = tmp_path / "empty.db"
    db_path.touch()
    monkeypatch.delenv("KTC_DATABASE_URL", raising=False)
    monkeypatch.setenv("KTC_DB_PATH", str(db_path))

    response = client.get("/scrape-dates")

    assert response.status_code == 503
    assert "no ktc_rankings table" in response.json()["detail"]


def test_database_url_takes_precedence_over_db_path(
    seeded_db, backend, monkeypatch, tmp_path: Path, client
) -> None:
    if backend != "sqlite":
        pytest.skip("checks SQLite path resolution")
    monkeypatch.setenv("KTC_DB_PATH", str(tmp_path / "ignored.db"))
    monkeypatch.setenv("KTC_DATABASE_URL", f"sqlite:///{seeded_db}")

    assert client.get("/scrape-dates").status_code == 200


def test_unreachable_postgres_returns_503_without_leaking_the_password(monkeypatch, client) -> None:
    monkeypatch.setenv("KTC_DATABASE_URL", "postgresql://ktc:s3cret@127.0.0.1:1/ktc")

    response = client.get("/rankings")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Database unavailable at postgresql://ktc:***@127.0.0.1:1/ktc"
    }


def test_postgres_without_the_driver_returns_501(monkeypatch, client) -> None:
    monkeypatch.setitem(sys.modules, "psycopg", None)
    monkeypatch.setenv("KTC_DATABASE_URL", "postgresql://ktc:pw@127.0.0.1:1/ktc")

    response = client.get("/rankings")

    assert response.status_code == 501
    assert "pip install 'ktc-webscraping[postgres]'" in response.json()["detail"]


def test_postgres_database_without_rankings_table_returns_503(monkeypatch, client) -> None:
    if not POSTGRES_URL:
        pytest.skip("set KTC_TEST_POSTGRES_URL to run the API on Postgres")
    _drop_postgres_rankings()
    monkeypatch.setenv("KTC_DATABASE_URL", POSTGRES_URL)

    response = client.get("/scrape-dates")

    assert response.status_code == 503
    assert "no ktc_rankings table" in response.json()["detail"]
