from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, TypeAlias

from .models import DatabaseConfig, PlayerRecord

if TYPE_CHECKING:
    import psycopg

DatabaseConnection: TypeAlias = "sqlite3.Connection | psycopg.Connection"


@dataclass(frozen=True)
class SqlDialect:
    """The few SQL details that differ between SQLite and Postgres."""

    placeholder: str
    id_column: str
    float_type: str


SQLITE = SqlDialect(
    placeholder="?", id_column="INTEGER PRIMARY KEY AUTOINCREMENT", float_type="REAL"
)
POSTGRES = SqlDialect(
    placeholder="%s",
    id_column="BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY",
    float_type="DOUBLE PRECISION",
)

RANKING_COLUMNS = (
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
)


def build_database_config(
    db_path: Path | str | None = None,
    database_url: str | None = None,
) -> DatabaseConfig:
    """Resolve database settings from either an explicit URL or local SQLite path."""

    resolved_database_url = database_url or ""
    if resolved_database_url:
        if resolved_database_url.startswith("sqlite:///"):
            sqlite_path = Path(resolved_database_url.removeprefix("sqlite:///"))
            return DatabaseConfig(
                url=resolved_database_url,
                scheme="sqlite",
                sqlite_path=sqlite_path,
            )
        if resolved_database_url.startswith("postgresql://") or resolved_database_url.startswith(
            "postgres://"
        ):
            return DatabaseConfig(
                url=resolved_database_url,
                scheme="postgresql",
                sqlite_path=None,
            )
        raise ValueError(f"Unsupported database URL scheme: {resolved_database_url}")

    resolved_db_path = Path(db_path or "db/ktc.db")
    return DatabaseConfig(
        url=f"sqlite:///{resolved_db_path}",
        scheme="sqlite",
        sqlite_path=resolved_db_path,
    )


def player_to_row(player: PlayerRecord) -> tuple:
    """Convert a player record into the row shape expected by SQLite inserts."""

    return (
        player.scrape_date,
        player.player_name,
        player.position,
        player.rank_overall,
        player.rank_position,
        player.team,
        player.source,
        player.age,
        player.tier,
        player.value,
        player.scraped_at,
    )


def validate_player_records(players: list[PlayerRecord]) -> None:
    for index, player in enumerate(players):
        if not player.scrape_date:
            raise ValueError(f"Player record at index {index} is missing scrape_date")
        if not player.player_name.strip():
            raise ValueError(f"Player record at index {index} is missing player_name")
        if not player.position.strip():
            raise ValueError(f"Player record at index {index} is missing position")
        if not player.source.strip():
            raise ValueError(f"Player record at index {index} is missing source")


def create_table_sql(dialect: SqlDialect) -> str:
    return f"""
        CREATE TABLE IF NOT EXISTS ktc_rankings (
            id {dialect.id_column},
            scrape_date TEXT NOT NULL,
            player_name TEXT,
            position TEXT,
            rank_overall INTEGER,
            rank_position INTEGER,
            team TEXT,
            source TEXT NOT NULL,
            age {dialect.float_type},
            tier INTEGER,
            value {dialect.float_type},
            scraped_at TEXT
        )
        """


CREATE_UNIQUE_INDEX_SQL = """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_ktc_rankings_scrape_date_player_source
    ON ktc_rankings (scrape_date, player_name, source)
    """


def upsert_sql(dialect: SqlDialect) -> str:
    placeholders = ", ".join([dialect.placeholder] * len(RANKING_COLUMNS))
    return f"""
        INSERT INTO ktc_rankings ({", ".join(RANKING_COLUMNS)})
        VALUES ({placeholders})
        ON CONFLICT (scrape_date, player_name, source) DO UPDATE SET
            position = excluded.position,
            rank_overall = excluded.rank_overall,
            rank_position = excluded.rank_position,
            team = excluded.team,
            age = excluded.age,
            tier = excluded.tier,
            value = excluded.value,
            scraped_at = excluded.scraped_at
        """


def dialect_for(conn: DatabaseConnection) -> SqlDialect:
    return SQLITE if isinstance(conn, sqlite3.Connection) else POSTGRES


def create_connection(db_file: Path | str, database_url: str | None = None) -> DatabaseConnection:
    """Open the configured database (SQLite or Postgres) and ensure the schema exists."""

    database_config = build_database_config(db_path=db_file, database_url=database_url)
    if database_config.scheme == "postgresql":
        conn = _connect_postgres(database_config.url)
    else:
        assert database_config.sqlite_path is not None
        database_config.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(database_config.sqlite_path)

    dialect = dialect_for(conn)
    cursor = conn.cursor()
    cursor.execute(create_table_sql(dialect))
    cursor.execute(CREATE_UNIQUE_INDEX_SQL)
    if dialect is SQLITE:
        # Retire the table used by the original prototype scraper.
        cursor.execute("DROP TABLE IF EXISTS players")
        cursor.execute("DROP INDEX IF EXISTS idx_players_player_name_scraped_at")
    conn.commit()
    return conn


def _connect_postgres(url: str) -> psycopg.Connection:
    try:
        import psycopg
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Postgres support needs psycopg: pip install 'ktc-webscraping[postgres]'"
        ) from exc
    return psycopg.connect(url, connect_timeout=10)


def prune_snapshot_sql(dialect: SqlDialect, keep_count: int) -> str:
    keep = ", ".join([dialect.placeholder] * keep_count)
    return (
        f"DELETE FROM ktc_rankings WHERE scrape_date = {dialect.placeholder} "
        f"AND source = {dialect.placeholder} AND player_name NOT IN ({keep})"
    )


def insert_player_data(conn: DatabaseConnection, players: list[PlayerRecord]) -> None:
    """Store a batch as the complete snapshot for each of its scrape dates.

    A batch is one scrape run. Rerunning a date that is already stored replaces
    that day's snapshot: players who dropped out of the rankings since the
    earlier run are removed, and the rest are upserted in place (keeping their
    ids). Without the prune step a same-day rerun would mix two runs, leaving
    stale players behind with duplicate ranks. Other dates are never touched,
    and everything happens in one transaction.
    """

    validate_player_records(players)
    if not players:
        return

    snapshots: dict[tuple[str, str], set[str]] = {}
    for player in players:
        snapshots.setdefault((player.scrape_date, player.source), set()).add(player.player_name)

    dialect = dialect_for(conn)
    cursor = conn.cursor()
    try:
        for (scrape_date, source), names in snapshots.items():
            cursor.execute(
                prune_snapshot_sql(dialect, len(names)), (scrape_date, source, *sorted(names))
            )
        cursor.executemany(upsert_sql(dialect), [player_to_row(p) for p in players])
    except Exception:
        conn.rollback()
        raise
    conn.commit()
