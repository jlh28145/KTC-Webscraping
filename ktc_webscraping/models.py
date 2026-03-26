from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DatabaseConfig:
    url: str
    scheme: str
    sqlite_path: Path | None


@dataclass(frozen=True)
class PlayerRecord:
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
    scraped_at: str


@dataclass(frozen=True)
class ScrapeConfig:
    base_url: str
    page_count: int
    min_rows_per_page: int
    retry_attempts: int
    db_path: Path
