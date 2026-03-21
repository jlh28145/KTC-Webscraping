from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PlayerRecord:
    rank: int | None
    player_name: str
    position: str
    position_rank: int | None
    team: str | None
    age: float | None
    tier: int | None
    value: float | None
    scraped_at: str


@dataclass(frozen=True)
class ScrapeConfig:
    base_url: str
    page_count: int
    min_rows_per_page: int
    db_path: Path
