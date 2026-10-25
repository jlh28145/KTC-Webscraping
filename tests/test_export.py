import sqlite3
from pathlib import Path

import pytest

from ktc_webscraping import export
from ktc_webscraping.load import create_connection, insert_player_data
from ktc_webscraping.models import PlayerRecord


def _record(scrape_date: str, name: str, position: str, rank: int | None, value: float):
    return PlayerRecord(
        scrape_date=scrape_date,
        player_name=name,
        position=position,
        rank_overall=rank,
        rank_position=None if rank is None else 1,
        team=None if position == "PICK" else "DET",
        source="keeptradecut",
        age=None if position == "PICK" else 24.6,
        tier=1,
        value=value,
        scraped_at=f"{scrape_date}T17:00:00+00:00",
    )


@pytest.fixture
def history_db(tmp_path: Path) -> Path:
    """Two days of history; the latest day mixes ranked players with an unranked pick."""

    path = tmp_path / "history" / "ktc.db"
    conn = create_connection(path)
    insert_player_data(
        conn,
        [
            _record("2026-10-24", "Josh Allen", "QB", 1, 9999.0),
            _record("2026-10-24", "Jahmyr Gibbs", "RB", 2, 9998.0),
        ],
    )
    insert_player_data(
        conn,
        [
            _record("2026-10-25", "Jahmyr Gibbs", "RB", 1, 9999.0),
            _record("2026-10-25", "2027 Early 1st", "PICK", None, 6871.0),
            _record("2026-10-25", "Josh Allen", "QB", 2, 9995.0),
        ],
    )
    conn.close()
    return path


def _rows(db: Path, sql: str):
    conn = sqlite3.connect(db)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def test_export_keeps_only_the_latest_snapshot(history_db: Path, tmp_path: Path) -> None:
    output = tmp_path / "publish" / "ktc.db"
    output.parent.mkdir()

    latest, count = export.export_latest_snapshot(history_db, output)

    assert (latest, count) == ("2026-10-25", 3)
    assert _rows(output, "SELECT DISTINCT scrape_date FROM ktc_rankings") == [("2026-10-25",)]


def test_export_matches_the_single_snapshot_contract(history_db: Path, tmp_path: Path) -> None:
    """Same table, same schema, ids from 1 in scrape order, values copied unchanged."""

    output = tmp_path / "ktc.db"

    export.export_latest_snapshot(history_db, output)

    schema = "SELECT sql FROM sqlite_master WHERE name = 'ktc_rankings'"
    assert _rows(output, schema) == _rows(history_db, schema)
    assert _rows(output, "SELECT name FROM sqlite_master WHERE type = 'table'") == [
        ("ktc_rankings",),
        ("sqlite_sequence",),
    ]
    columns = ", ".join(export.RANKING_COLUMNS)
    assert _rows(output, f"SELECT id, {columns} FROM ktc_rankings ORDER BY id") == [
        (index, *row)
        for index, row in enumerate(
            _rows(
                history_db,
                f"SELECT {columns} FROM ktc_rankings WHERE scrape_date = '2026-10-25' ORDER BY id",
            ),
            start=1,
        )
    ]


def test_export_replaces_an_existing_output_file(history_db: Path, tmp_path: Path) -> None:
    output = tmp_path / "ktc.db"
    output.write_bytes(b"stale bytes from a previous run")

    export.export_latest_snapshot(history_db, output)

    assert _rows(output, "SELECT COUNT(*) FROM ktc_rankings") == [(3,)]


def test_export_rejects_a_missing_history_database(tmp_path: Path) -> None:
    output = tmp_path / "ktc.db"

    with pytest.raises(FileNotFoundError, match="History database not found"):
        export.export_latest_snapshot(tmp_path / "missing.db", output)

    assert not output.exists()


def test_export_rejects_an_empty_history_and_leaves_no_output(tmp_path: Path) -> None:
    empty = tmp_path / "empty.db"
    create_connection(empty).close()
    output = tmp_path / "ktc.db"

    with pytest.raises(ValueError, match="no rankings to export"):
        export.export_latest_snapshot(empty, output)

    assert not output.exists()


def test_summary_lists_ranked_players_before_unranked_picks(
    history_db: Path, tmp_path: Path
) -> None:
    summary = export.publish(history_db, tmp_path / "publish")

    assert summary == (
        "Published snapshot: ktc.db (latest scrape date only)\n"
        "Latest scrape date: 2026-10-25\n"
        "Rows for latest scrape date: 3\n"
        "History: 5 rows across 2 scrape dates (published separately as the ktc-history artifact)\n"
        "\n"
        "Top 10 rows from latest scrape:\n"
        "1. Jahmyr Gibbs (RB) team=DET\n"
        "2. Josh Allen (QB) team=DET\n"
        "None. 2027 Early 1st (PICK) team=None\n"
    )
    assert (tmp_path / "publish" / "scrape_summary.txt").read_text(encoding="utf-8") == summary
    assert (tmp_path / "publish" / "ktc.db").is_file()


def test_main_publishes_and_prints_the_summary(history_db: Path, tmp_path: Path, capsys) -> None:
    output_dir = tmp_path / "publish"

    assert export.main(["--history", str(history_db), "--output-dir", str(output_dir)]) == 0

    assert "Latest scrape date: 2026-10-25" in capsys.readouterr().out
    assert sorted(path.name for path in output_dir.iterdir()) == ["ktc.db", "scrape_summary.txt"]


def test_main_reports_a_missing_history_database(tmp_path: Path, capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        export.main(["--history", str(tmp_path / "missing.db"), "--output-dir", str(tmp_path)])

    assert exc_info.value.code == 1
    assert "Export failed: History database not found" in capsys.readouterr().err
