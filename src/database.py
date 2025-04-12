# src/database.py
import sqlite3

def create_connection(db_file):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rank INTEGER,
        player_name TEXT,
        position TEXT,
        position_rank INTEGER,
        team TEXT,
        age INTEGER,
        tier INTEGER,
        value INTEGER,
        scraped_at TEXT
    )
    """)
    conn.commit()
    return conn

def insert_player_data(conn, players):
    cursor = conn.cursor()
    cursor.executemany("""
    INSERT INTO players 
    (rank, player_name, position, position_rank, team, age, tier, value, scraped_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, players)
    conn.commit()
