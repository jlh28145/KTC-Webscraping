import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel

from ktc_webscraping.config import load_runtime_config
from ktc_webscraping.load import build_database_config

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


def get_db_path() -> Path:
    """Resolve the SQLite file from the same KTC_* settings the scraper uses."""

    runtime_config = load_runtime_config()
    database_config = build_database_config(
        db_path=runtime_config.db_path, database_url=runtime_config.database_url
    )
    if database_config.sqlite_path is None:
        raise HTTPException(status_code=501, detail="The API currently supports SQLite only.")
    return database_config.sqlite_path


def get_connection(
    db_path: Annotated[Path, Depends(get_db_path)],
) -> Iterator[sqlite3.Connection]:
    """Open a read-only connection, failing clearly if no scrape has been stored yet."""

    if not db_path.exists():
        raise HTTPException(
            status_code=503,
            detail=f"Database not found at {db_path}. Run the scraper first.",
        )

    conn = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        has_table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'ktc_rankings'"
        ).fetchone()
        if not has_table:
            raise HTTPException(
                status_code=503,
                detail="Database has no ktc_rankings table. Run the scraper first.",
            )
        yield conn
    finally:
        conn.close()


Connection = Annotated[sqlite3.Connection, Depends(get_connection)]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/scrape-dates", response_model=list[str])
def list_scrape_dates(conn: Connection) -> list[str]:
    """Return every stored snapshot date, newest first."""

    rows = conn.execute(
        "SELECT DISTINCT scrape_date FROM ktc_rankings ORDER BY scrape_date DESC"
    ).fetchall()
    return [row["scrape_date"] for row in rows]


@app.get("/rankings", response_model=list[Ranking])
def read_rankings(
    conn: Connection,
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
    return [dict(row) for row in conn.execute(query, values).fetchall()]


@app.get("/rankings/{ranking_id}", response_model=Ranking)
def get_ranking(ranking_id: int, conn: Connection) -> dict:
    row = conn.execute("SELECT * FROM ktc_rankings WHERE id = ?", (ranking_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Ranking {ranking_id} not found")
    return dict(row)


@app.get("/player", response_model=list[Ranking])
def get_player_history(
    conn: Connection,
    name: str = Query(..., min_length=1, description="Case-insensitive name fragment."),
) -> list[dict]:
    """Return every stored snapshot for players matching ``name``, newest first."""

    escaped = name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    rows = conn.execute(
        """
        SELECT *
        FROM ktc_rankings
        WHERE LOWER(player_name) LIKE LOWER(?) ESCAPE '\\'
        ORDER BY scrape_date DESC, rank_overall ASC
        """,
        (f"%{escaped}%",),
    ).fetchall()
    return [dict(row) for row in rows]
