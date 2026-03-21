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
    rank_node = row.select_one(".rank-number")
    name_node = row.select_one(".player-name a")
    position_node = row.select_one(".position-team .position")
    tier_node = row.select_one(".player-tier")
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

        age_node = row.select_one(".age")
        age_text = age_node.get_text(strip=True) if age_node else None
        if age_text:
            age = safe_float(age_text.replace(" y.o.", ""))

    return PlayerRecord(
        rank=safe_int(rank_node.get_text(strip=True)),
        player_name=name_node.get_text(strip=True),
        position=position,
        position_rank=position_rank,
        team=team,
        age=age,
        tier=safe_int(tier_node.get_text(strip=True).replace("Tier ", "")),
        value=safe_float(value_node.get_text(strip=True)),
        scraped_at=scrape_timestamp,
    )


def parse_player_text_lines(lines: list[str], scrape_timestamp: str) -> PlayerRecord | None:
    cleaned = [line.strip() for line in lines if line and line.strip() and line.strip() != "\u2022"]
    if len(cleaned) < 5 or not cleaned[0].isdigit():
        return None

    rank = safe_int(cleaned[0])
    player_name = cleaned[1]
    team = None

    position_index = 2
    if len(cleaned) > 3 and re.fullmatch(r"[A-Z]{2,3}|FA|R FA", cleaned[2]):
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
            rank=rank,
            player_name=player_name,
            position="PICK",
            position_rank=None,
            team=team,
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
        rank=rank,
        player_name=player_name,
        position=position,
        position_rank=position_rank,
        team=team,
        age=age,
        tier=tier,
        value=value,
        scraped_at=scrape_timestamp,
    )


def split_name_and_team(player_line: str) -> tuple[str, str | None]:
    match = re.match(r"^(?P<name>.+?)(?P<team>R FA|FA|[A-Z]{2,3})$", player_line.strip())
    if not match:
        return player_line.strip(), None
    return match.group("name").strip(), match.group("team")


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

        rank = safe_int(rank_text)
        player_line = lines[index + 1]
        position_text = lines[index + 2]
        player_name, team = split_name_and_team(player_line)

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


def parse_player_rows(page_html: str, scrape_timestamp: str) -> list[PlayerRecord]:
    soup = BeautifulSoup(page_html, "html.parser")
    player_rows = soup.select("#rankings-page-rankings .onePlayer")

    players: list[PlayerRecord] = []
    for row in player_rows:
        record = parse_player_row(row, scrape_timestamp)
        if record is not None:
            players.append(record)

    if players:
        return players

    return parse_player_rows_from_text(extract_rankings_text_lines(page_html), scrape_timestamp)
