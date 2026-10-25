import re

from bs4 import BeautifulSoup

from .models import PlayerRecord


def safe_float(text: str | None) -> float | None:
    if text is None:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def safe_int(text: str | None) -> int | None:
    if text is None:
        return None
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def normalize_position(position_text: str) -> tuple[str, int | None]:
    if "PICK" in position_text:
        return position_text, None

    position = "".join(filter(str.isalpha, position_text))
    position_rank = safe_int("".join(filter(str.isdigit, position_text)))
    return position, position_rank


def parse_player_row(row, scrape_timestamp: str) -> PlayerRecord | None:
    """Parse one ``.onePlayer`` row from either the legacy or the current layout.

    The current layout (2026-10) moved tier into ``.player-info .position`` and
    age into a second ``.position-team .position`` paragraph; the legacy layout
    used dedicated ``.player-tier`` and ``.age`` nodes.
    """

    rank_node = row.select_one(".rank-number")
    name_node = row.select_one(".player-name a")
    position_node = row.select_one(".position-team .position")
    tier_node = row.select_one(".player-tier") or row.select_one(".player-info .position")
    value_node = row.select_one(".value")

    if not all([rank_node, name_node, position_node, tier_node, value_node]):
        return None

    position_text = position_node.get_text(strip=True)
    position, position_rank = normalize_position(position_text)

    team = None
    age = None
    if "PICK" not in position_text:
        team_node = row.select_one(".player-team")
        team = team_node.get_text(strip=True) if team_node else None

        age_text = _find_age_text(row)
        if age_text:
            age = safe_float(age_text.replace(" y.o.", ""))

    return PlayerRecord(
        scrape_date=scrape_timestamp.split("T", maxsplit=1)[0],
        player_name=name_node.get_text(strip=True),
        position=position,
        rank_overall=safe_int(rank_node.get_text(strip=True)),
        rank_position=position_rank,
        team=team,
        source="keeptradecut",
        age=age,
        tier=safe_int(tier_node.get_text(strip=True).replace("Tier ", "")),
        value=safe_float(value_node.get_text(strip=True)),
        scraped_at=scrape_timestamp,
    )


def _find_age_text(row) -> str | None:
    age_node = row.select_one(".age")
    if age_node:
        return age_node.get_text(strip=True)
    for node in row.select(".position-team .position"):
        text = node.get_text(strip=True)
        if text.endswith("y.o."):
            return text
    return None


def parse_player_text_lines(lines: list[str], scrape_timestamp: str) -> PlayerRecord | None:
    cleaned = [line.strip() for line in lines if line and line.strip() and line.strip() != "\u2022"]
    if len(cleaned) < 5 or not cleaned[0].isdigit():
        return None

    rank = safe_int(cleaned[0])
    player_name = cleaned[1]
    team = None

    position_index = 2
    if len(cleaned) > 3 and re.fullmatch(r"[A-Z]{3}|FA|R FA", cleaned[2]):
        team = cleaned[2]
        position_index = 3

    if position_index >= len(cleaned):
        return None

    position_text = cleaned[position_index]
    if team is None:
        player_name, team = split_name_and_team(player_name)

    tier_index = next((i for i, line in enumerate(cleaned) if line.startswith("Tier ")), None)
    if tier_index is None:
        return None

    value = safe_float(cleaned[-1])
    tier = safe_int(cleaned[tier_index].replace("Tier ", ""))

    if position_text == "PICK":
        return PlayerRecord(
            scrape_date=scrape_timestamp.split("T", maxsplit=1)[0],
            player_name=player_name,
            position="PICK",
            rank_overall=rank,
            rank_position=None,
            team=team,
            source="keeptradecut",
            age=None,
            tier=tier,
            value=value,
            scraped_at=scrape_timestamp,
        )

    age_index = next((i for i, line in enumerate(cleaned) if line.endswith("y.o.")), None)
    age = None
    if age_index is not None:
        age = safe_float(cleaned[age_index].replace(" y.o.", ""))

    position, position_rank = normalize_position(position_text)
    return PlayerRecord(
        scrape_date=scrape_timestamp.split("T", maxsplit=1)[0],
        player_name=player_name,
        position=position,
        rank_overall=rank,
        rank_position=position_rank,
        team=team,
        source="keeptradecut",
        age=age,
        tier=tier,
        value=value,
        scraped_at=scrape_timestamp,
    )


def split_name_and_team(player_line: str) -> tuple[str, str | None]:
    """Split a text-layout line like ``"Kenneth Walker IIIKCC"`` into name and team.

    KeepTradeCut uses three-letter team codes (``KCC``, ``SFO``) plus ``FA`` and
    ``R FA``. Free-agent suffixes are checked first so a name ending in capitals
    (``"Kenneth Walker IIIFA"``) isn't misread as ``"...II"`` plus ``"IFA"``.
    """

    line = player_line.strip()
    for pattern in (r"(?P<name>.+?)(?P<team>R FA|FA)", r"(?P<name>.+)(?P<team>[A-Z]{3})"):
        match = re.fullmatch(pattern, line)
        if match:
            return match.group("name").strip(), match.group("team")
    return line, None


def extract_rankings_text_lines(page_html: str) -> list[str]:
    soup = BeautifulSoup(page_html, "html.parser")
    text = soup.get_text("\n", strip=True)
    return [line.strip() for line in text.splitlines() if line.strip()]


def parse_player_rows_from_text(lines: list[str], scrape_timestamp: str) -> list[PlayerRecord]:
    header = ["RANK", "PLAYER NAME", "POS", "AGE", "TIER", "30DT", "30 DAY TREND", "VALUE"]

    start_index = -1
    for index in range(len(lines) - len(header) + 1):
        window = [line for line in lines[index : index + 8] if line != "\u2022"]
        if window[: len(header)] == header:
            start_index = index + 8
            break

    if start_index == -1:
        return []

    players: list[PlayerRecord] = []
    index = start_index
    while index < len(lines):
        rank_text = lines[index]
        if not rank_text.isdigit():
            index += 1
            continue

        if index + 2 >= len(lines):
            break

        position_text = lines[index + 2]

        if position_text == "PICK":
            record = parse_player_text_lines(lines[index : index + 6], scrape_timestamp)
            if record is None:
                break
            players.append(record)
            index += 6
            continue

        record = parse_player_text_lines(lines[index : index + 8], scrape_timestamp)
        if record is None:
            break
        players.append(record)
        index += 8

    return players


def parse_player_rows_with_parser(
    page_html: str, scrape_timestamp: str
) -> tuple[list[PlayerRecord], str]:
    """Parse a page and name the parser that produced the records.

    ``"html"`` is the primary row parser; ``"html-text"`` means no row matched
    and the page text was parsed instead, which usually signals a layout change.
    """

    soup = BeautifulSoup(page_html, "html.parser")
    player_rows = soup.select("#rankings-page-rankings .onePlayer")

    players: list[PlayerRecord] = []
    for row in player_rows:
        record = parse_player_row(row, scrape_timestamp)
        if record is not None:
            players.append(record)

    if players:
        return players, "html"

    text_records = parse_player_rows_from_text(
        extract_rankings_text_lines(page_html), scrape_timestamp
    )
    return text_records, "html-text"


def parse_player_rows(page_html: str, scrape_timestamp: str) -> list[PlayerRecord]:
    return parse_player_rows_with_parser(page_html, scrape_timestamp)[0]
