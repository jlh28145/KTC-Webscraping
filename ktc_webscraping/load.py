import sqlite3
from pathlib import Path

from .models import PlayerRecord


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


def create_connection(db_file: Path | str) -> sqlite3.Connection:
    db_path = Path(db_file)
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
