from bs4 import BeautifulSoup

from ktc_webscraping.models import PlayerRecord
from ktc_webscraping.transform import (
    extract_rankings_text_lines,
    normalize_position,
    parse_player_row,
    parse_player_rows,
    parse_player_rows_from_text,
    parse_player_text_lines,
    safe_float,
    safe_int,
    split_name_and_team,
)


def test_safe_number_helpers_handle_invalid_values() -> None:
    assert safe_int("12") == 12
    assert safe_int("bad") is None
    assert safe_float("10.5") == 10.5
    assert safe_float(None) is None


def test_normalize_position_handles_ranked_players_and_picks() -> None:
    assert normalize_position("WR12") == ("WR", 12)
    assert normalize_position("PICK") == ("PICK", None)


def test_split_name_and_team_handles_suffix_team_codes() -> None:
    assert split_name_and_team("Bijan RobinsonATL") == ("Bijan Robinson", "ATL")
    assert split_name_and_team("2027 Early 1stFA") == ("2027 Early 1st", "FA")
    assert split_name_and_team("Unmatched Name") == ("Unmatched Name", None)


def test_parse_player_row_from_legacy_html(legacy_row_html: str, scrape_timestamp: str) -> None:
    soup = BeautifulSoup(legacy_row_html, "html.parser")
    row = soup.select_one(".onePlayer")

    record = parse_player_row(row, scrape_timestamp)

    assert record == PlayerRecord(
        rank=1,
        player_name="Josh Allen",
        position="QB",
        position_rank=1,
        team="BUF",
        age=29.8,
        tier=1,
        value=9989.0,
        scraped_at=scrape_timestamp,
    )


def test_parse_player_row_returns_none_for_malformed_row(scrape_timestamp: str) -> None:
    soup = BeautifulSoup(
        "<div class='onePlayer'><div class='rank-number'>1</div></div>", "html.parser"
    )
    row = soup.select_one(".onePlayer")

    assert parse_player_row(row, scrape_timestamp) is None


def test_parse_player_text_lines_handles_standard_player(scrape_timestamp: str) -> None:
    lines = ["1", "Bijan Robinson", "ATL", "RB1", "24.1 y.o.", "Tier 1", "1", "9999"]

    record = parse_player_text_lines(lines, scrape_timestamp)

    assert record == PlayerRecord(
        rank=1,
        player_name="Bijan Robinson",
        position="RB",
        position_rank=1,
        team="ATL",
        age=24.1,
        tier=1,
        value=9999.0,
        scraped_at=scrape_timestamp,
    )


def test_parse_player_text_lines_handles_pick_rows(scrape_timestamp: str) -> None:
    lines = ["2", "2027 Early 1stFA", "PICK", "Tier 5", "1", "6810"]

    record = parse_player_text_lines(lines, scrape_timestamp)

    assert record == PlayerRecord(
        rank=2,
        player_name="2027 Early 1st",
        position="PICK",
        position_rank=None,
        team="FA",
        age=None,
        tier=5,
        value=6810.0,
        scraped_at=scrape_timestamp,
    )


def test_parse_player_text_lines_normalizes_whitespace(scrape_timestamp: str) -> None:
    lines = [
        "  3  ",
        "  Ja'Marr Chase  ",
        " CIN ",
        " WR1 ",
        " 26.0 y.o. ",
        " Tier 2 ",
        " 2 ",
        " 9770 ",
    ]

    record = parse_player_text_lines(lines, scrape_timestamp)

    assert record is not None
    assert record.player_name == "Ja'Marr Chase"
    assert record.team == "CIN"
    assert record.position == "WR"
    assert record.position_rank == 1


def test_parse_player_text_lines_returns_none_for_missing_tier(scrape_timestamp: str) -> None:
    lines = ["1", "Bijan Robinson", "ATL", "RB1", "24.1 y.o.", "9999"]

    assert parse_player_text_lines(lines, scrape_timestamp) is None


def test_parse_player_rows_uses_legacy_html_when_available(
    legacy_row_html: str, scrape_timestamp: str
) -> None:
    records = parse_player_rows(legacy_row_html, scrape_timestamp)

    assert len(records) == 1
    assert records[0].player_name == "Josh Allen"


def test_extract_rankings_text_lines_and_parse_current_layout(
    text_layout_html: str, scrape_timestamp: str
) -> None:
    lines = extract_rankings_text_lines(text_layout_html)

    records = parse_player_rows_from_text(lines, scrape_timestamp)

    assert len(records) == 2
    assert records[0].player_name == "Bijan Robinson"
    assert records[0].team == "ATL"
    assert records[1].position == "PICK"
    assert records[1].position_rank is None
    assert records[1].team == "FA"


def test_parse_player_rows_falls_back_to_current_text_layout(
    text_layout_html: str, scrape_timestamp: str
) -> None:
    records = parse_player_rows(text_layout_html, scrape_timestamp)

    assert len(records) == 2
    assert all(isinstance(record, PlayerRecord) for record in records)


def test_parse_player_rows_preserves_duplicate_rows(scrape_timestamp: str) -> None:
    lines = [
        "RANK",
        "PLAYER NAME",
        "POS",
        "AGE",
        "TIER",
        "30DT",
        "30 DAY TREND",
        "VALUE",
        "1",
        "Bijan RobinsonATL",
        "RB1",
        "•",
        "24.1 y.o.",
        "Tier 1",
        "1",
        "9999",
        "1",
        "Bijan RobinsonATL",
        "RB1",
        "•",
        "24.1 y.o.",
        "Tier 1",
        "1",
        "9999",
    ]

    records = parse_player_rows_from_text(lines, scrape_timestamp)

    assert len(records) == 2
    assert records[0] == records[1]
