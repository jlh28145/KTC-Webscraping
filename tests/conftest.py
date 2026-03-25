from pathlib import Path

import pytest

from ktc_webscraping.models import PlayerRecord


@pytest.fixture
def scrape_timestamp() -> str:
    return "2026-03-21T00:00:00"


@pytest.fixture
def legacy_row_html() -> str:
    return """
    <div id="rankings-page-rankings">
      <div class="onePlayer">
        <div class="rank-number">1</div>
        <div class="player-name"><a>Josh Allen</a></div>
        <div class="position-team">
          <span class="position">QB1</span>
        </div>
        <div class="player-team">BUF</div>
        <div class="age">29.8 y.o.</div>
        <div class="player-tier">Tier 1</div>
        <div class="value">9989</div>
      </div>
    </div>
    """


@pytest.fixture
def text_layout_html() -> str:
    return """
    <html>
      <body>
        <div id="rankings-page-rankings">
          <div>RANK</div>
          <div>PLAYER NAME</div>
          <div>POS</div>
          <div>AGE</div>
          <div>TIER</div>
          <div>30DT</div>
          <div>30 DAY TREND</div>
          <div>VALUE</div>
          <div>1</div>
          <div>Bijan RobinsonATL</div>
          <div>RB1</div>
          <div>•</div>
          <div>24.1 y.o.</div>
          <div>Tier 1</div>
          <div>1</div>
          <div>9999</div>
          <div>2</div>
          <div>2027 Early 1stFA</div>
          <div>PICK</div>
          <div>Tier 5</div>
          <div>1</div>
          <div>6810</div>
        </div>
      </body>
    </html>
    """


@pytest.fixture
def sample_player(scrape_timestamp: str) -> PlayerRecord:
    return PlayerRecord(
        scrape_date="2026-03-21",
        player_name="Josh Allen",
        position="QB",
        rank_overall=1,
        rank_position=1,
        team="BUF",
        source="keeptradecut",
        age=29.8,
        tier=1,
        value=9989.0,
        scraped_at=scrape_timestamp,
    )


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "ktc_test.db"
