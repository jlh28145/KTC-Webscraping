"""Integration tests for the Postgres load path.

They run against a real server when KTC_TEST_POSTGRES_URL is set (CI provides a
postgres:17 service container) and are skipped otherwise. Each test starts from
an empty ktc_rankings table, so point this at a disposable database only.
"""

import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from ktc_webscraping import cli
from ktc_webscraping.load import create_connection, insert_player_data
from ktc_webscraping.models import PlayerRecord, ScrapeConfig, ScrapeResult

POSTGRES_URL = os.getenv("KTC_TEST_POSTGRES_URL")

if not POSTGRES_URL and os.getenv("CI"):
    # CI provides a Postgres service; a missing URL there is misconfiguration, not a skip.
    pytest.fail("KTC_TEST_POSTGRES_URL is not set in CI", pytrace=False)

pytestmark = pytest.mark.skipif(
    not POSTGRES_URL, reason="set KTC_TEST_POSTGRES_URL to run Postgres integration tests"
)


def _drop_rankings_table() -> None:
    import psycopg

    with psycopg.connect(POSTGRES_URL, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS ktc_rankings")


@pytest.fixture
def pg_conn(tmp_path: Path):
    _drop_rankings_table()
    conn = create_connection(tmp_path / "unused.db", database_url=POSTGRES_URL)
    yield conn
    conn.close()
    _drop_rankings_table()


def _record(scrape_date: str, name: str, rank: int | None, value: float, **overrides):
    fields = dict(
        scrape_date=scrape_date,
        player_name=name,
        position="QB",
        rank_overall=rank,
        rank_position=rank,
        team="BUF",
        source="keeptradecut",
        age=30.4,
        tier=1,
        value=value,
        scraped_at=f"{scrape_date}T13:00:00+00:00",
    )
    fields.update(overrides)
    return PlayerRecord(**fields)


def _rows(conn, sql: str, params=()):
    return conn.execute(sql, params).fetchall()


def test_create_connection_builds_matching_schema(pg_conn) -> None:
    columns = _rows(
        pg_conn,
        """
        SELECT column_name, data_type, is_nullable, is_identity
        FROM information_schema.columns
        WHERE table_name = 'ktc_rankings'
        ORDER BY ordinal_position
        """,
    )
    index = _rows(
        pg_conn,
        "SELECT indexdef FROM pg_indexes WHERE indexname = "
        "'idx_ktc_rankings_scrape_date_player_source'",
    )

    assert columns == [
        ("id", "bigint", "NO", "YES"),
        ("scrape_date", "text", "NO", "NO"),
        ("player_name", "text", "YES", "NO"),
        ("position", "text", "YES", "NO"),
        ("rank_overall", "integer", "YES", "NO"),
        ("rank_position", "integer", "YES", "NO"),
        ("team", "text", "YES", "NO"),
        ("source", "text", "NO", "NO"),
        ("age", "double precision", "YES", "NO"),
        ("tier", "integer", "YES", "NO"),
        ("value", "double precision", "YES", "NO"),
        ("scraped_at", "text", "YES", "NO"),
    ]
    assert "UNIQUE INDEX" in index[0][0]
    assert "(scrape_date, player_name, source)" in index[0][0]


def test_insert_round_trips_types_and_nulls(pg_conn) -> None:
    pick = _record(
        "2026-10-19",
        "2027 Early 1st",
        None,
        6871.0,
        position="PICK",
        team=None,
        age=None,
    )
    insert_player_data(pg_conn, [_record("2026-10-19", "Josh Allen", 1, 9999.0), pick])

    rows = _rows(
        pg_conn,
        "SELECT player_name, rank_overall, team, age, value FROM ktc_rankings ORDER BY id",
    )

    assert rows == [
        ("Josh Allen", 1, "BUF", 30.4, 9999.0),
        ("2027 Early 1st", None, None, None, 6871.0),
    ]


def test_same_day_rerun_upserts_instead_of_duplicating(pg_conn) -> None:
    insert_player_data(pg_conn, [_record("2026-10-19", "Josh Allen", 2, 9990.0)])
    insert_player_data(
        pg_conn,
        [
            _record(
                "2026-10-19",
                "Josh Allen",
                1,
                9999.0,
                scraped_at="2026-10-19T18:00:00+00:00",
            )
        ],
    )

    assert _rows(pg_conn, "SELECT rank_overall, value, scraped_at FROM ktc_rankings") == [
        (1, 9999.0, "2026-10-19T18:00:00+00:00")
    ]


def test_history_accumulates_across_scrape_dates(pg_conn) -> None:
    insert_player_data(pg_conn, [_record("2026-10-18", "Josh Allen", 1, 9999.0)])
    insert_player_data(pg_conn, [_record("2026-10-19", "Josh Allen", 2, 9995.0)])

    assert _rows(
        pg_conn, "SELECT scrape_date, rank_overall FROM ktc_rankings ORDER BY scrape_date"
    ) == [("2026-10-18", 1), ("2026-10-19", 2)]


def test_reconnecting_keeps_existing_rows(pg_conn, tmp_path: Path) -> None:
    insert_player_data(pg_conn, [_record("2026-10-19", "Josh Allen", 1, 9999.0)])

    second = create_connection(tmp_path / "unused.db", database_url=POSTGRES_URL)
    count = _rows(second, "SELECT COUNT(*) FROM ktc_rankings")[0][0]
    second.close()

    assert count == 1


def test_invalid_batch_writes_nothing(pg_conn) -> None:
    batch = [_record("2026-10-19", "Josh Allen", 1, 9999.0), _record("2026-10-19", " ", 2, 1.0)]

    with pytest.raises(ValueError, match="index 1 is missing player_name"):
        insert_player_data(pg_conn, batch)

    assert _rows(pg_conn, "SELECT COUNT(*) FROM ktc_rankings")[0][0] == 0


def test_cli_run_writes_to_postgres(pg_conn, monkeypatch, tmp_path: Path, capsys) -> None:
    players = [_record("2026-10-19", "Josh Allen", 1, 9999.0)]
    monkeypatch.setattr(
        cli,
        "scrape_rankings",
        lambda *, config, headless: ScrapeResult(records=players, page_count=1),
    )
    config = ScrapeConfig(
        base_url="https://example.com?page={page}",
        page_count=1,
        min_rows_per_page=1,
        retry_attempts=0,
        db_path=tmp_path / "ignored.db",
        database_url=POSTGRES_URL,
    )

    assert cli.run(config=config) == 0

    assert _rows(pg_conn, "SELECT player_name FROM ktc_rankings") == [("Josh Allen",)]
    output = capsys.readouterr().out
    assert "using postgresql" in output
    password = urlsplit(POSTGRES_URL).password
    if password:
        assert f":{password}@" not in output
        assert ":***@" in output
    assert not (tmp_path / "ignored.db").exists()


def test_same_day_rerun_replaces_the_snapshot(pg_conn) -> None:
    insert_player_data(
        pg_conn,
        [
            _record("2026-10-25", "Harrison Bryant", 462, 451.0),
            _record("2026-10-25", "Ray-Ray McCloud", 463, 452.0),
        ],
    )
    insert_player_data(
        pg_conn,
        [
            _record("2026-10-25", "Harrison Bryant", 463, 450.0),
            _record("2026-10-25", "Terrell Jennings", 464, 449.0),
        ],
    )

    assert _rows(
        pg_conn, "SELECT player_name, rank_overall FROM ktc_rankings ORDER BY rank_overall"
    ) == [("Harrison Bryant", 463), ("Terrell Jennings", 464)]
