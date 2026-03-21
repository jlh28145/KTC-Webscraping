import sqlite3

from ktc_webscraping.load import create_connection, insert_player_data
from ktc_webscraping.models import PlayerRecord


def test_create_connection_creates_database_and_players_table(temp_db_path) -> None:
    conn = create_connection(temp_db_path)

    table_name = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'players'"
    ).fetchone()
    conn.close()

    assert temp_db_path.exists()
    assert table_name == ("players",)


def test_create_connection_creates_expected_players_schema(temp_db_path) -> None:
    conn = create_connection(temp_db_path)

    columns = conn.execute("PRAGMA table_info(players)").fetchall()
    conn.close()

    assert columns == [
        (0, "id", "INTEGER", 0, None, 1),
        (1, "rank", "INTEGER", 0, None, 0),
        (2, "player_name", "TEXT", 0, None, 0),
        (3, "position", "TEXT", 0, None, 0),
        (4, "position_rank", "INTEGER", 0, None, 0),
        (5, "team", "TEXT", 0, None, 0),
        (6, "age", "REAL", 0, None, 0),
        (7, "tier", "INTEGER", 0, None, 0),
        (8, "value", "REAL", 0, None, 0),
        (9, "scraped_at", "TEXT", 0, None, 0),
    ]


def test_create_connection_creates_unique_index_for_player_and_scrape_timestamp(temp_db_path) -> None:
    conn = create_connection(temp_db_path)

    indexes = conn.execute("PRAGMA index_list(players)").fetchall()
    conn.close()

    assert any(index[1] == "idx_players_player_name_scraped_at" and index[2] == 1 for index in indexes)


def test_insert_player_data_persists_player_records(temp_db_path, sample_player: PlayerRecord) -> None:
    conn = create_connection(temp_db_path)

    insert_player_data(conn, [sample_player])
    row = conn.execute(
        """
        SELECT rank, player_name, position, position_rank, team, age, tier, value, scraped_at
        FROM players
        """
    ).fetchone()
    conn.close()

    assert row == (
        1,
        "Josh Allen",
        "QB",
        1,
        "BUF",
        29.8,
        1,
        9989.0,
        sample_player.scraped_at,
    )


def test_insert_player_data_accepts_empty_input(temp_db_path) -> None:
    conn = create_connection(temp_db_path)

    insert_player_data(conn, [])
    count = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    conn.close()

    assert count == 0


def test_load_layer_persists_multiple_rows_and_scrape_dates(temp_db_path, scrape_timestamp: str) -> None:
    conn = create_connection(temp_db_path)
    players = [
        PlayerRecord(1, "Josh Allen", "QB", 1, "BUF", 29.8, 1, 9989.0, scrape_timestamp),
        PlayerRecord(2, "Bijan Robinson", "RB", 1, "ATL", 24.1, 1, 9999.0, "2026-03-22T00:00:00"),
    ]

    insert_player_data(conn, players)
    rows = conn.execute("SELECT player_name, scraped_at FROM players ORDER BY rank").fetchall()
    conn.close()

    assert rows == [
        ("Josh Allen", scrape_timestamp),
        ("Bijan Robinson", "2026-03-22T00:00:00"),
    ]


def test_load_layer_preserves_float_fields(temp_db_path, scrape_timestamp: str) -> None:
    conn = create_connection(temp_db_path)
    player = PlayerRecord(3, "Test Player", "WR", 8, "SEA", 24.3, 2, 7777.5, scrape_timestamp)

    insert_player_data(conn, [player])
    age, value = conn.execute("SELECT age, value FROM players WHERE player_name = ?", ("Test Player",)).fetchone()
    conn.close()

    assert isinstance(age, float)
    assert isinstance(value, float)
    assert age == 24.3
    assert value == 7777.5


def test_load_layer_prevents_duplicate_player_and_scrape_timestamp(temp_db_path, sample_player: PlayerRecord) -> None:
    conn = create_connection(temp_db_path)

    insert_player_data(conn, [sample_player, sample_player])
    count = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    conn.close()

    assert count == 1


def test_load_layer_upserts_existing_player_for_same_scrape_timestamp(temp_db_path, scrape_timestamp: str) -> None:
    conn = create_connection(temp_db_path)
    original = PlayerRecord(1, "Josh Allen", "QB", 1, "BUF", 29.8, 1, 9989.0, scrape_timestamp)
    updated = PlayerRecord(2, "Josh Allen", "QB", 1, "BUF", 29.9, 1, 9995.0, scrape_timestamp)

    insert_player_data(conn, [original])
    insert_player_data(conn, [updated])
    row = conn.execute(
        "SELECT rank, age, value FROM players WHERE player_name = ? AND scraped_at = ?",
        ("Josh Allen", scrape_timestamp),
    ).fetchone()
    count = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    conn.close()

    assert count == 1
    assert row == (2, 29.9, 9995.0)


def test_load_layer_returns_sqlite_connection(temp_db_path) -> None:
    conn = create_connection(temp_db_path)
    try:
        assert isinstance(conn, sqlite3.Connection)
    finally:
        conn.close()
