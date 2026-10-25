"""Publish the latest snapshot from the history database for downstream consumers.

The scheduled scrape keeps every day's rankings in a history database, but the
``scheduled-scrape-*`` artifact contract (a downstream repo commits the file
to Git) is one snapshot per ``ktc.db``. This module writes
that single-snapshot database plus a human-readable ``scrape_summary.txt``.
"""

import argparse
import sqlite3
from contextlib import closing
from pathlib import Path

from .load import RANKING_COLUMNS, create_connection

SNAPSHOT_FILENAME = "ktc.db"
SUMMARY_FILENAME = "scrape_summary.txt"


def export_latest_snapshot(history_db: Path, output_db: Path) -> tuple[str, int]:
    """Copy the latest scrape date's rows into a fresh database at ``output_db``.

    Rows keep their original order and get ids from 1, matching the
    one-snapshot files the scheduled scrape published before history was kept.
    Returns the exported scrape date and row count.
    """

    if not history_db.is_file():
        raise FileNotFoundError(f"History database not found: {history_db}")

    output_db.unlink(missing_ok=True)
    conn = create_connection(output_db)
    try:
        conn.execute("ATTACH DATABASE ? AS history", (str(history_db),))
        latest = conn.execute("SELECT MAX(scrape_date) FROM history.ktc_rankings").fetchone()[0]
        if latest is None:
            raise ValueError(f"History database has no rankings to export: {history_db}")

        columns = ", ".join(RANKING_COLUMNS)
        cursor = conn.execute(
            f"INSERT INTO ktc_rankings ({columns}) "
            f"SELECT {columns} FROM history.ktc_rankings WHERE scrape_date = ? ORDER BY id",
            (latest,),
        )
        exported = cursor.rowcount
        conn.commit()
        conn.execute("DETACH DATABASE history")
    except Exception:
        conn.close()
        output_db.unlink(missing_ok=True)
        raise
    conn.close()
    return latest, exported


def build_summary(history_db: Path, snapshot_db: Path) -> str:
    """Describe the published snapshot and the history it was cut from."""

    with closing(sqlite3.connect(history_db)) as history:
        history_rows, history_dates = history.execute(
            "SELECT COUNT(*), COUNT(DISTINCT scrape_date) FROM ktc_rankings"
        ).fetchone()

    with closing(sqlite3.connect(snapshot_db)) as snapshot:
        latest, latest_rows = snapshot.execute(
            "SELECT MAX(scrape_date), COUNT(*) FROM ktc_rankings"
        ).fetchone()
        # Draft picks have no overall rank; SQLite sorts NULL first, so push them last.
        top_rows = snapshot.execute(
            """
            SELECT player_name, rank_overall, position, team
            FROM ktc_rankings
            ORDER BY rank_overall IS NULL, rank_overall, value DESC
            LIMIT 10
            """
        ).fetchall()

    lines = [
        f"Published snapshot: {SNAPSHOT_FILENAME} (latest scrape date only)",
        f"Latest scrape date: {latest}",
        f"Rows for latest scrape date: {latest_rows}",
        f"History: {history_rows} rows across {history_dates} scrape dates "
        "(published separately as the ktc-history artifact)",
        "",
        "Top 10 rows from latest scrape:",
    ]
    lines += [f"{rank}. {name} ({position}) team={team}" for name, rank, position, team in top_rows]
    return "\n".join(lines) + "\n"


def publish(history_db: Path, output_dir: Path) -> str:
    """Write the snapshot database and summary into ``output_dir``; return the summary."""

    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_db = output_dir / SNAPSHOT_FILENAME
    export_latest_snapshot(history_db, snapshot_db)
    summary = build_summary(history_db, snapshot_db)
    (output_dir / SUMMARY_FILENAME).write_text(summary, encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Publish the latest rankings snapshot and a summary from a history database."
    )
    parser.add_argument("--history", type=Path, required=True, help="History SQLite database.")
    parser.add_argument(
        "--output-dir", type=Path, required=True, help="Directory for ktc.db and the summary."
    )
    args = parser.parse_args(argv)

    try:
        summary = publish(args.history, args.output_dir)
    except (FileNotFoundError, ValueError) as exc:
        parser.exit(1, f"Export failed: {exc}\n")
    print(summary, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
