import sqlite3
from pathlib import Path

import pytest

from ktc_webscraping.load import (
    build_database_config,
    create_connection,
    insert_player_data,
    validate_player_records,
)
from ktc_webscraping.models import PlayerRecord


def test_build_database_config_defaults_to_sqlite_path(temp_db_path) -> None:
    config = build_database_config(db_path=temp_db_path)

    assert config.scheme == "sqlite"
    assert config.sqlite_path == temp_db_path
    assert config.url == f"sqlite:///{temp_db_path}"


def test_build_database_config_accepts_sqlite_database_url(tmp_path: Path) -> None:
    db_path = tmp_path / "configured.db"

    config = build_database_config(database_url=f"sqlite:///{db_path}")

    assert config.scheme == "sqlite"
    assert config.sqlite_path == db_path


def test_build_database_config_accepts_postgres_database_url() -> None:
    config = build_database_config(
        database_url="postgresql://user:password@localhost:5432/ktc_rankings"
    )

    assert config.scheme == "postgresql"
    assert config.sqlite_path is None


def test_build_database_config_rejects_unknown_scheme() -> None:
    with pytest.raises(ValueError):
        build_database_config(database_url="mysql://localhost/example")


def test_create_connection_creates_database_and_rankings_table(temp_db_path) -> None:
    conn = create_connection(temp_db_path)

    table_name = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'ktc_rankings'"
    ).fetchone()
    conn.close()

    assert temp_db_path.exists()
    assert table_name == ("ktc_rankings",)


def test_create_connection_raises_for_postgres_until_client_is_added(temp_db_path) -> None:
    with pytest.raises(NotImplementedError):
        create_connection(
            temp_db_path,
            database_url="postgresql://user:password@localhost:5432/ktc_rankings",
        )


def test_create_connection_creates_expected_rankings_schema(temp_db_path) -> None:
    conn = create_connection(temp_db_path)

    columns = conn.execute("PRAGMA table_info(ktc_rankings)").fetchall()
    conn.close()

    assert columns == [
        (0, "id", "INTEGER", 0, None, 1),
        (1, "scrape_date", "TEXT", 1, None, 0),
        (2, "player_name", "TEXT", 0, None, 0),
        (3, "position", "TEXT", 0, None, 0),
        (4, "rank_overall", "INTEGER", 0, None, 0),
        (5, "rank_position", "INTEGER", 0, None, 0),
        (6, "team", "TEXT", 0, None, 0),
        (7, "source", "TEXT", 1, None, 0),
        (8, "age", "REAL", 0, None, 0),
        (9, "tier", "INTEGER", 0, None, 0),
        (10, "value", "REAL", 0, None, 0),
        (11, "scraped_at", "TEXT", 0, None, 0),
    ]


def test_create_connection_creates_unique_index_for_scrape_date_player_and_source(
    temp_db_path,
) -> None:
    conn = create_connection(temp_db_path)

    indexes = conn.execute("PRAGMA index_list(ktc_rankings)").fetchall()
    conn.close()

    assert any(
        index[1] == "idx_ktc_rankings_scrape_date_player_source" and index[2] == 1
        for index in indexes
    )


def test_create_connection_retires_legacy_players_table(temp_db_path) -> None:
    conn = sqlite3.connect(temp_db_path)
    conn.execute("CREATE TABLE players (id INTEGER PRIMARY KEY, player_name TEXT)")
    conn.execute(
        "CREATE UNIQUE INDEX idx_players_player_name_scraped_at ON players (player_name, id)"
    )
    conn.commit()
    conn.close()

    conn = create_connection(temp_db_path)
    legacy_table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'players'"
    ).fetchone()
    legacy_index = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'index' AND name = 'idx_players_player_name_scraped_at'
        """
    ).fetchone()
    rankings_table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'ktc_rankings'"
    ).fetchone()
    conn.close()

    assert legacy_table is None
    assert legacy_index is None
    assert rankings_table == ("ktc_rankings",)


def test_insert_player_data_persists_player_records(
    temp_db_path, sample_player: PlayerRecord
) -> None:
    conn = create_connection(temp_db_path)

    insert_player_data(conn, [sample_player])
    row = conn.execute(
        """
        SELECT
            scrape_date,
            player_name,
            position,
            rank_overall,
            rank_position,
            team,
            source,
            age,
            tier,
            value,
            scraped_at
        FROM ktc_rankings
        """
    ).fetchone()
    conn.close()

    assert row == (
        "2026-03-21",
        "Josh Allen",
        "QB",
        1,
        1,
        "BUF",
        "keeptradecut",
        29.8,
        1,
        9989.0,
        sample_player.scraped_at,
    )


def test_insert_player_data_accepts_empty_input(temp_db_path) -> None:
    conn = create_connection(temp_db_path)

    insert_player_data(conn, [])
    count = conn.execute("SELECT COUNT(*) FROM ktc_rankings").fetchone()[0]
    conn.close()

    assert count == 0


def test_validate_player_records_rejects_blank_player_name(scrape_timestamp: str) -> None:
    players = [
        PlayerRecord(
            "2026-03-21",
            "   ",
            "QB",
            1,
            1,
            "BUF",
            "keeptradecut",
            29.8,
            1,
            9989.0,
            scrape_timestamp,
        )
    ]

    with pytest.raises(ValueError, match="missing player_name"):
        validate_player_records(players)


def test_insert_player_data_rejects_blank_source(temp_db_path, scrape_timestamp: str) -> None:
    conn = create_connection(temp_db_path)
    players = [
        PlayerRecord(
            "2026-03-21",
            "Josh Allen",
            "QB",
            1,
            1,
            "BUF",
            " ",
            29.8,
            1,
            9989.0,
            scrape_timestamp,
        )
    ]

    with pytest.raises(ValueError, match="missing source"):
        insert_player_data(conn, players)

    conn.close()


def test_load_layer_persists_multiple_rows_and_scrape_dates(
    temp_db_path, scrape_timestamp: str
) -> None:
    conn = create_connection(temp_db_path)
    players = [
        PlayerRecord(
            "2026-03-21",
            "Josh Allen",
            "QB",
            1,
            1,
            "BUF",
            "keeptradecut",
            29.8,
            1,
            9989.0,
            scrape_timestamp,
        ),
        PlayerRecord(
            "2026-03-22",
            "Bijan Robinson",
            "RB",
            2,
            1,
            "ATL",
            "keeptradecut",
            24.1,
            1,
            9999.0,
            "2026-03-22T00:00:00",
        ),
    ]

    insert_player_data(conn, players)
    rows = conn.execute(
        "SELECT player_name, scrape_date FROM ktc_rankings ORDER BY rank_overall"
    ).fetchall()
    conn.close()

    assert rows == [
        ("Josh Allen", "2026-03-21"),
        ("Bijan Robinson", "2026-03-22"),
    ]


def test_load_layer_preserves_float_fields(temp_db_path, scrape_timestamp: str) -> None:
    conn = create_connection(temp_db_path)
    player = PlayerRecord(
        "2026-03-21",
        "Test Player",
        "WR",
        3,
        8,
        "SEA",
        "keeptradecut",
        24.3,
        2,
        7777.5,
        scrape_timestamp,
    )

    insert_player_data(conn, [player])
    age, value = conn.execute(
        "SELECT age, value FROM ktc_rankings WHERE player_name = ?",
        ("Test Player",),
    ).fetchone()
    conn.close()

    assert isinstance(age, float)
    assert isinstance(value, float)
    assert age == 24.3
    assert value == 7777.5


def test_load_layer_prevents_duplicate_player_and_scrape_date(
    temp_db_path, sample_player: PlayerRecord
) -> None:
    conn = create_connection(temp_db_path)

    insert_player_data(conn, [sample_player, sample_player])
    count = conn.execute("SELECT COUNT(*) FROM ktc_rankings").fetchone()[0]
    conn.close()

    assert count == 1


def test_load_layer_upserts_existing_player_for_same_scrape_date(
    temp_db_path, scrape_timestamp: str
) -> None:
    conn = create_connection(temp_db_path)
    original = PlayerRecord(
        "2026-03-21",
        "Josh Allen",
        "QB",
        1,
        1,
        "BUF",
        "keeptradecut",
        29.8,
        1,
        9989.0,
        scrape_timestamp,
    )
    updated = PlayerRecord(
        "2026-03-21",
        "Josh Allen",
        "QB",
        2,
        1,
        "BUF",
        "keeptradecut",
        29.9,
        1,
        9995.0,
        scrape_timestamp,
    )

    insert_player_data(conn, [original])
    insert_player_data(conn, [updated])
    row = conn.execute(
        """
        SELECT rank_overall, age, value
        FROM ktc_rankings
        WHERE scrape_date = ? AND player_name = ? AND source = ?
        """,
        ("2026-03-21", "Josh Allen", "keeptradecut"),
    ).fetchone()
    count = conn.execute("SELECT COUNT(*) FROM ktc_rankings").fetchone()[0]
    conn.close()

    assert count == 1
    assert row == (2, 29.9, 9995.0)


def test_load_layer_accumulates_historical_rows_across_scrape_dates(temp_db_path) -> None:
    conn = create_connection(temp_db_path)
    first = PlayerRecord(
        "2026-03-21",
        "Josh Allen",
        "QB",
        1,
        1,
        "BUF",
        "keeptradecut",
        29.8,
        1,
        9989.0,
        "2026-03-21T00:00:00",
    )
    second = PlayerRecord(
        "2026-03-22",
        "Josh Allen",
        "QB",
        2,
        1,
        "BUF",
        "keeptradecut",
        29.8,
        1,
        9975.0,
        "2026-03-22T00:00:00",
    )

    insert_player_data(conn, [first, second])
    rows = conn.execute(
        """
        SELECT scrape_date, rank_overall
        FROM ktc_rankings
        WHERE player_name = ?
        ORDER BY scrape_date
        """,
        ("Josh Allen",),
    ).fetchall()
    conn.close()

    assert rows == [("2026-03-21", 1), ("2026-03-22", 2)]


def test_load_layer_returns_sqlite_connection(temp_db_path) -> None:
    conn = create_connection(temp_db_path)
    try:
        assert isinstance(conn, sqlite3.Connection)
    finally:
        conn.close()
