import sqlite3
from pathlib import Path

from .models import PlayerRecord


def player_to_row(player: PlayerRecord) -> tuple:
    return (
        player.rank,
        player.player_name,
        player.position,
        player.position_rank,
        player.team,
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
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rank INTEGER,
            player_name TEXT,
            position TEXT,
            position_rank INTEGER,
            team TEXT,
            age REAL,
            tier INTEGER,
            value REAL,
            scraped_at TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_players_player_name_scraped_at
        ON players (player_name, scraped_at)
        """
    )
    conn.commit()
    return conn


def insert_player_data(conn: sqlite3.Connection, players: list[PlayerRecord]) -> None:
    cursor = conn.cursor()
    cursor.executemany(
        """
        INSERT INTO players
        (rank, player_name, position, position_rank, team, age, tier, value, scraped_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(player_name, scraped_at) DO UPDATE SET
            rank = excluded.rank,
            position = excluded.position,
            position_rank = excluded.position_rank,
            team = excluded.team,
            age = excluded.age,
            tier = excluded.tier,
            value = excluded.value
        """,
        [player_to_row(player) for player in players],
    )
    conn.commit()
