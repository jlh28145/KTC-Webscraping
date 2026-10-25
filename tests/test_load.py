import sqlite3
import sys
from pathlib import Path

import pytest

from ktc_webscraping.load import (
    POSTGRES,
    RANKING_COLUMNS,
    SQLITE,
    build_database_config,
    create_connection,
    create_table_sql,
    dialect_for,
    insert_player_data,
    upsert_sql,
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


def test_create_connection_explains_missing_postgres_driver(monkeypatch, temp_db_path) -> None:
    monkeypatch.setitem(sys.modules, "psycopg", None)

    with pytest.raises(RuntimeError, match=r"pip install 'ktc-webscraping\[postgres\]'"):
        create_connection(
            temp_db_path,
            database_url="postgresql://user:password@localhost:5432/ktc_rankings",
        )


@pytest.mark.parametrize(
    ("dialect", "placeholder", "id_column", "float_type"),
    [
        (SQLITE, "?", "INTEGER PRIMARY KEY AUTOINCREMENT", "REAL"),
        (POSTGRES, "%s", "BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY", "DOUBLE PRECISION"),
    ],
)
def test_dialects_render_backend_specific_sql(dialect, placeholder, id_column, float_type) -> None:
    upsert = upsert_sql(dialect)

    assert upsert.count(placeholder) == len(RANKING_COLUMNS)
    assert "ON CONFLICT (scrape_date, player_key, source) DO UPDATE" in upsert
    assert f"id {id_column}" in create_table_sql(dialect)
    assert f"value {float_type}" in create_table_sql(dialect)


def test_dialect_for_detects_sqlite_connections(temp_db_path) -> None:
    conn = create_connection(temp_db_path)

    assert dialect_for(conn) is SQLITE
    assert dialect_for(object()) is POSTGRES
    conn.close()


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
        (12, "ktc_player_id", "INTEGER", 0, None, 0),
        (13, "player_key", "TEXT", 0, None, 0),
    ]


def test_create_connection_creates_unique_index_on_player_key(temp_db_path) -> None:
    conn = create_connection(temp_db_path)

    indexes = {row[1]: row for row in conn.execute("PRAGMA index_list(ktc_rankings)")}
    key_columns = [
        row[2]
        for row in conn.execute("PRAGMA index_info(idx_ktc_rankings_scrape_date_player_key_source)")
    ]
    conn.close()

    assert indexes["idx_ktc_rankings_scrape_date_player_key_source"][2] == 1
    assert "idx_ktc_rankings_scrape_date_player_source" not in indexes
    assert key_columns == ["scrape_date", "player_key", "source"]


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
        "2026-03-21T18:30:00",
    )

    insert_player_data(conn, [original])
    insert_player_data(conn, [updated])
    row = conn.execute(
        """
        SELECT rank_overall, age, value, scraped_at
        FROM ktc_rankings
        WHERE scrape_date = ? AND player_name = ? AND source = ?
        """,
        ("2026-03-21", "Josh Allen", "keeptradecut"),
    ).fetchone()
    count = conn.execute("SELECT COUNT(*) FROM ktc_rankings").fetchone()[0]
    conn.close()

    assert count == 1
    assert row == (2, 29.9, 9995.0, "2026-03-21T18:30:00")


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


@pytest.mark.parametrize(
    ("database_url", "expected"),
    [
        (
            "postgresql://ktc:s3cr%40t@ep-cool-name.neon.tech:5432/ktc?sslmode=require",
            "postgresql://ktc:***@ep-cool-name.neon.tech:5432/ktc?sslmode=require",
        ),
        ("postgresql://ktc@localhost/ktc", "postgresql://ktc@localhost/ktc"),
        ("sqlite:///db/ktc.db", "sqlite:///db/ktc.db"),
    ],
)
def test_display_url_masks_passwords(database_url: str, expected: str) -> None:
    assert build_database_config(database_url=database_url).display_url == expected


def _snapshot_player(scrape_date: str, name: str, rank: int, source: str = "keeptradecut"):
    return PlayerRecord(
        scrape_date, name, "WR", rank, rank, "FA", source, 27.0, 18, 450.0, f"{scrape_date}T17:00"
    )


def test_same_day_rerun_replaces_the_snapshot(temp_db_path) -> None:
    """Regression: a manual rerun on 2026-10-25 left a player from the earlier run behind."""

    conn = create_connection(temp_db_path)
    insert_player_data(
        conn,
        [
            _snapshot_player("2026-10-25", "Harrison Bryant", 462),
            _snapshot_player("2026-10-25", "Ray-Ray McCloud", 463),
            _snapshot_player("2026-10-25", "Tyler Johnson", 464),
        ],
    )
    ids_before = dict(conn.execute("SELECT player_name, id FROM ktc_rankings").fetchall())

    insert_player_data(
        conn,
        [
            _snapshot_player("2026-10-25", "Tyler Johnson", 462),
            _snapshot_player("2026-10-25", "Harrison Bryant", 463),
            _snapshot_player("2026-10-25", "Terrell Jennings", 464),
        ],
    )
    rows = conn.execute(
        "SELECT player_name, rank_overall, id FROM ktc_rankings ORDER BY rank_overall"
    ).fetchall()
    conn.close()

    assert [(name, rank) for name, rank, _ in rows] == [
        ("Tyler Johnson", 462),
        ("Harrison Bryant", 463),
        ("Terrell Jennings", 464),
    ]
    surviving_ids = {name: row_id for name, _, row_id in rows if name in ids_before}
    assert surviving_ids == {
        "Tyler Johnson": ids_before["Tyler Johnson"],
        "Harrison Bryant": ids_before["Harrison Bryant"],
    }


def test_snapshot_replace_leaves_other_dates_and_sources_alone(temp_db_path) -> None:
    conn = create_connection(temp_db_path)
    insert_player_data(
        conn,
        [
            _snapshot_player("2026-10-24", "Ray-Ray McCloud", 460),
            _snapshot_player("2026-10-25", "Ray-Ray McCloud", 463, source="other-source"),
            _snapshot_player("2026-10-25", "Ray-Ray McCloud", 463),
        ],
    )

    insert_player_data(conn, [_snapshot_player("2026-10-25", "Harrison Bryant", 463)])
    rows = conn.execute(
        "SELECT scrape_date, source, player_name FROM ktc_rankings ORDER BY scrape_date, source"
    ).fetchall()
    conn.close()

    assert rows == [
        ("2026-10-24", "keeptradecut", "Ray-Ray McCloud"),
        ("2026-10-25", "keeptradecut", "Harrison Bryant"),
        ("2026-10-25", "other-source", "Ray-Ray McCloud"),
    ]


def test_failed_batch_rolls_back_the_prune(temp_db_path, monkeypatch) -> None:
    conn = create_connection(temp_db_path)
    insert_player_data(conn, [_snapshot_player("2026-10-25", "Ray-Ray McCloud", 463)])

    def broken_upsert_sql(dialect):
        return "INSERT INTO no_such_table VALUES (1)"

    monkeypatch.setattr("ktc_webscraping.load.upsert_sql", broken_upsert_sql)
    with pytest.raises(sqlite3.OperationalError):
        insert_player_data(conn, [_snapshot_player("2026-10-25", "Harrison Bryant", 463)])

    names = conn.execute("SELECT player_name FROM ktc_rankings").fetchall()
    conn.close()
    assert names == [("Ray-Ray McCloud",)]


def _legacy_history_db(path) -> None:
    """A history table exactly as the scheduled scrape wrote it before player ids."""

    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE ktc_rankings (
            id INTEGER PRIMARY KEY AUTOINCREMENT, scrape_date TEXT NOT NULL, player_name TEXT,
            position TEXT, rank_overall INTEGER, rank_position INTEGER, team TEXT,
            source TEXT NOT NULL, age REAL, tier INTEGER, value REAL, scraped_at TEXT
        )
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX idx_ktc_rankings_scrape_date_player_source "
        "ON ktc_rankings (scrape_date, player_name, source)"
    )
    conn.executemany(
        "INSERT INTO ktc_rankings (scrape_date, player_name, position, rank_overall, source) "
        "VALUES (?, ?, 'RB', ?, 'keeptradecut')",
        [("2026-10-24", "Jahmyr Gibbs", 1), ("2026-10-24", "Bijan Robinson", 2)],
    )
    conn.commit()
    conn.close()


def test_create_connection_migrates_a_pre_id_history_table(temp_db_path) -> None:
    _legacy_history_db(temp_db_path)

    conn = create_connection(temp_db_path)
    rows = conn.execute(
        "SELECT id, player_name, ktc_player_id, player_key FROM ktc_rankings ORDER BY id"
    ).fetchall()
    indexes = [row[1] for row in conn.execute("PRAGMA index_list(ktc_rankings)")]
    conn.close()

    assert rows == [
        (1, "Jahmyr Gibbs", None, "name:Jahmyr Gibbs"),
        (2, "Bijan Robinson", None, "name:Bijan Robinson"),
    ]
    assert "idx_ktc_rankings_scrape_date_player_key_source" in indexes
    assert "idx_ktc_rankings_scrape_date_player_source" not in indexes


def test_migration_is_idempotent_and_new_rows_use_ids(temp_db_path) -> None:
    _legacy_history_db(temp_db_path)
    create_connection(temp_db_path).close()

    conn = create_connection(temp_db_path)
    insert_player_data(
        conn,
        [
            PlayerRecord(
                "2026-10-25",
                "Jahmyr Gibbs",
                "RB",
                1,
                1,
                "DET",
                "keeptradecut",
                24.6,
                1,
                9999.0,
                "2026-10-25T17:00:00+00:00",
                ktc_player_id=1415,
            )
        ],
    )
    rows = conn.execute(
        "SELECT scrape_date, player_key FROM ktc_rankings ORDER BY scrape_date, id"
    ).fetchall()
    conn.close()

    assert rows == [
        ("2026-10-24", "name:Jahmyr Gibbs"),
        ("2026-10-24", "name:Bijan Robinson"),
        ("2026-10-25", "ktc:1415"),
    ]


def test_two_players_sharing_a_name_are_kept_apart(temp_db_path) -> None:
    conn = create_connection(temp_db_path)
    twins = [
        PlayerRecord(
            "2026-10-25",
            "Josh Allen",
            position,
            rank,
            1,
            team,
            "keeptradecut",
            None,
            1,
            1000.0,
            "2026-10-25T17:00:00+00:00",
            ktc_player_id=player_id,
        )
        for position, rank, team, player_id in [("QB", 1, "BUF", 1001), ("LB", 400, "JAC", 2002)]
    ]

    insert_player_data(conn, twins)
    rows = conn.execute(
        "SELECT player_name, position, ktc_player_id FROM ktc_rankings ORDER BY rank_overall"
    ).fetchall()
    conn.close()

    assert rows == [("Josh Allen", "QB", 1001), ("Josh Allen", "LB", 2002)]


def test_player_key_prefers_the_ktc_id() -> None:
    record = PlayerRecord(
        "2026-10-25",
        "Josh Allen",
        "QB",
        1,
        1,
        "BUF",
        "keeptradecut",
        30.4,
        1,
        9999.0,
        "2026-10-25T17:00:00+00:00",
    )

    assert record.player_key == "name:Josh Allen"
    assert PlayerRecord(**{**record.__dict__, "ktc_player_id": 7}).player_key == "ktc:7"
