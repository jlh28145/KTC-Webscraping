import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, Query

app = FastAPI()
DB_PATH = Path(__file__).resolve().parents[1] / "db" / "ktc.db"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # This allows dict-like row access
    return conn


@app.get("/rankings", response_model=List[Dict])
def read_rankings(
    position: Optional[str] = Query(None),
    team: Optional[str] = Query(None),
    tier: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Build dynamic WHERE clause
    query = "SELECT * FROM players"
    filters = []
    values = []

    if position:
        filters.append("position = ?")
        values.append(position)
    if team:
        filters.append("team = ?")
        values.append(team)
    if tier is not None:
        filters.append("tier = ?")
        values.append(tier)

    if filters:
        query += " WHERE " + " AND ".join(filters)

    query += " ORDER BY rank ASC"

    # Pagination logic
    offset = (page - 1) * limit
    query += " LIMIT ? OFFSET ?"
    values.extend([limit, offset])

    cursor.execute(query, values)
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


# Get player by ID
@app.get("/rankings/{player_id}", response_model=Dict)
def get_player_by_id(player_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM players WHERE id = ?", (player_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return {"error": "Player not found"}


# Get player by Name (case-insensitive)
@app.get("/player", response_model=List[Dict])
def get_player_by_name(name: str = Query(...)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM players WHERE LOWER(player_name) LIKE LOWER(?)", (f"%{name}%",))
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]
