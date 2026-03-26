import sqlite3
from pathlib import Path

from .models import DatabaseConfig, PlayerRecord


def build_database_config(
    db_path: Path | str | None = None,
    database_url: str | None = None,
) -> DatabaseConfig:
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


def create_connection(db_file: Path | str, database_url: str | None = None) -> sqlite3.Connection:
    database_config = build_database_config(db_path=db_file, database_url=database_url)
    if database_config.scheme != "sqlite" or database_config.sqlite_path is None:
        raise NotImplementedError(
            "Postgres connectivity is not implemented yet. "
            "Use SQLite locally or add a Postgres client in Phase 6."
        )

    db_path = database_config.sqlite_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ktc_rankings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scrape_date TEXT NOT NULL,
            player_name TEXT,
            position TEXT,
            rank_overall INTEGER,
            rank_position INTEGER,
            team TEXT,
            source TEXT NOT NULL,
            age REAL,
            tier INTEGER,
            value REAL,
            scraped_at TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_ktc_rankings_scrape_date_player_source
        ON ktc_rankings (scrape_date, player_name, source)
        """
    )
    cursor.execute("DROP TABLE IF EXISTS players")
    cursor.execute("DROP INDEX IF EXISTS idx_players_player_name_scraped_at")
    conn.commit()
    return conn


def insert_player_data(conn: sqlite3.Connection, players: list[PlayerRecord]) -> None:
    cursor = conn.cursor()
    cursor.executemany(
        """
        INSERT INTO ktc_rankings
        (
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
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(scrape_date, player_name, source) DO UPDATE SET
            position = excluded.position,
            rank_overall = excluded.rank_overall,
            rank_position = excluded.rank_position,
            team = excluded.team,
            age = excluded.age,
            tier = excluded.tier,
            value = excluded.value
        """,
        [player_to_row(player) for player in players],
    )
    conn.commit()
