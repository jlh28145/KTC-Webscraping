import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel

from ktc_webscraping.config import load_runtime_config
from ktc_webscraping.load import POSTGRES, SQLITE, build_database_config
from ktc_webscraping.models import DatabaseConfig

app = FastAPI(
    title="KTC Rankings API",
    description="Read-only API over the historical KeepTradeCut rankings snapshots.",
)


class Ranking(BaseModel):
    """One persisted row from ``ktc_rankings``."""

    id: int
    scrape_date: str
    player_name: str
    position: str
    rank_overall: int | None
    rank_position: int | None
    team: str | None
    source: str
    age: float | None
    tier: int | None
    value: float | None
    scraped_at: str | None
    # Absent from databases written before player ids were collected.
    ktc_player_id: int | None = None
    player_key: str | None = None


@dataclass
class RankingsReader:
    """Runs the endpoints' SQL on SQLite or Postgres and returns plain dicts.

    Queries are written with ``?`` placeholders and translated to the
    backend's style here, so each endpoint's SQL exists once.
    """

    conn: Any
    placeholder: str

    def fetch_all(self, sql: str, params: tuple | list = ()) -> list[dict]:
        cursor = self.conn.execute(sql.replace("?", self.placeholder), params)
        return [dict(row) for row in cursor.fetchall()]

    def fetch_one(self, sql: str, params: tuple | list = ()) -> dict | None:
        rows = self.fetch_all(sql, params)
        return rows[0] if rows else None


NO_DATA = "Run the scraper first."


def get_database_config() -> DatabaseConfig:
    """Resolve the database from the same KTC_* settings the scraper uses."""

    runtime_config = load_runtime_config()
    return build_database_config(
        db_path=runtime_config.db_path, database_url=runtime_config.database_url
    )


def get_reader(
    database_config: Annotated[DatabaseConfig, Depends(get_database_config)],
) -> Iterator[RankingsReader]:
    """Open a read-only connection, failing clearly if no scrape has been stored yet."""

    if database_config.scheme == "postgresql":
        yield from _postgres_reader(database_config)
    else:
        assert database_config.sqlite_path is not None
        yield from _sqlite_reader(database_config.sqlite_path)


def _sqlite_reader(db_path: Path) -> Iterator[RankingsReader]:
    if not db_path.exists():
        raise HTTPException(status_code=503, detail=f"Database not found at {db_path}. {NO_DATA}")

    conn = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        has_table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'ktc_rankings'"
        ).fetchone()
        if not has_table:
            raise HTTPException(
                status_code=503, detail=f"Database has no ktc_rankings table. {NO_DATA}"
            )
        yield RankingsReader(conn, SQLITE.placeholder)
    finally:
        conn.close()


def _postgres_reader(database_config: DatabaseConfig) -> Iterator[RankingsReader]:
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=501,
            detail="Postgres support needs psycopg: pip install 'ktc-webscraping[postgres]'",
        ) from exc

    try:
        conn = psycopg.connect(database_config.url, row_factory=dict_row, connect_timeout=5)
    except psycopg.OperationalError as exc:
        # display_url masks the password; the driver's message can include the host.
        raise HTTPException(
            status_code=503, detail=f"Database unavailable at {database_config.display_url}"
        ) from exc

    conn.read_only = True
    try:
        has_table = conn.execute(
            "SELECT to_regclass('ktc_rankings') IS NOT NULL AS present"
        ).fetchone()["present"]
        if not has_table:
            raise HTTPException(
                status_code=503, detail=f"Database has no ktc_rankings table. {NO_DATA}"
            )
        yield RankingsReader(conn, POSTGRES.placeholder)
    finally:
        conn.close()


Reader = Annotated[RankingsReader, Depends(get_reader)]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/scrape-dates", response_model=list[str])
def list_scrape_dates(reader: Reader) -> list[str]:
    """Return every stored snapshot date, newest first."""

    rows = reader.fetch_all(
        "SELECT DISTINCT scrape_date FROM ktc_rankings ORDER BY scrape_date DESC"
    )
    return [row["scrape_date"] for row in rows]


@app.get("/rankings", response_model=list[Ranking])
def read_rankings(
    reader: Reader,
    position: str | None = Query(None, description="QB, RB, WR, TE, or PICK."),
    team: str | None = Query(None, description="KeepTradeCut team code, e.g. KCC."),
    tier: int | None = Query(None, ge=1),
    scrape_date: str | None = Query(
        None, description="Snapshot date (YYYY-MM-DD). Defaults to the latest scrape."
    ),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
) -> list[dict]:
    """Return one snapshot's rankings, filtered and paginated in rank order."""

    filters = []
    values: list[str | int] = []

    if scrape_date:
        filters.append("scrape_date = ?")
        values.append(scrape_date)
    else:
        filters.append("scrape_date = (SELECT MAX(scrape_date) FROM ktc_rankings)")
    if position:
        filters.append("position = ?")
        values.append(position.upper())
    if team:
        filters.append("team = ?")
        values.append(team.upper())
    if tier is not None:
        filters.append("tier = ?")
        values.append(tier)

    # Picks have no overall rank on KeepTradeCut, so order them by value after ranked rows.
    query = (
        "SELECT * FROM ktc_rankings WHERE "
        + " AND ".join(filters)
        + " ORDER BY rank_overall IS NULL, rank_overall, value DESC LIMIT ? OFFSET ?"
    )
    values.extend([limit, (page - 1) * limit])
    return reader.fetch_all(query, values)


@app.get("/rankings/{ranking_id}", response_model=Ranking)
def get_ranking(ranking_id: int, reader: Reader) -> dict:
    row = reader.fetch_one("SELECT * FROM ktc_rankings WHERE id = ?", (ranking_id,))
    if row is None:
        raise HTTPException(status_code=404, detail=f"Ranking {ranking_id} not found")
    return row


@app.get("/player", response_model=list[Ranking])
def get_player_history(
    reader: Reader,
    name: str = Query(..., min_length=1, description="Case-insensitive name fragment."),
) -> list[dict]:
    """Return every stored snapshot for players matching ``name``, newest first."""

    escaped = name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    # NULL ranks (picks) last on both backends; SQLite and Postgres default differently.
    return reader.fetch_all(
        """
        SELECT *
        FROM ktc_rankings
        WHERE LOWER(player_name) LIKE LOWER(?) ESCAPE '\\'
        ORDER BY scrape_date DESC, rank_overall IS NULL, rank_overall
        """,
        (f"%{escaped}%",),
    )
