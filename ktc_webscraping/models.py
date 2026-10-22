from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


@dataclass(frozen=True)
class DatabaseConfig:
    """Resolved database connection settings for the current runtime."""

    url: str
    scheme: str
    sqlite_path: Path | None

    @property
    def display_url(self) -> str:
        """The URL with any password masked, safe for logs and console output."""

        parts = urlsplit(self.url)
        if parts.password is None:
            return self.url
        host = parts.hostname or ""
        if parts.port:
            host = f"{host}:{parts.port}"
        netloc = f"{parts.username}:***@{host}"
        return urlunsplit(parts._replace(netloc=netloc))


@dataclass(frozen=True)
class PlayerRecord:
    """Normalized ranking row shared between extract, transform, and load layers."""

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
    """Runtime settings for one scrape execution."""

    base_url: str
    page_count: int
    min_rows_per_page: int
    retry_attempts: int
    db_path: Path
    row_count_tolerance: int = 10
    page_delay_seconds: float = 3.0
    row_count_poll_timeout: int = 15
    database_url: str | None = None
