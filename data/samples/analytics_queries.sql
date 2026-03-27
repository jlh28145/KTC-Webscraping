-- Top 10 players from the latest scrape date.
SELECT player_name, position, rank_overall, team, value
FROM ktc_rankings
WHERE scrape_date = (SELECT MAX(scrape_date) FROM ktc_rankings)
ORDER BY rank_overall ASC
LIMIT 10;

-- Count players by position for the latest scrape date.
SELECT position, COUNT(*) AS player_count
FROM ktc_rankings
WHERE scrape_date = (SELECT MAX(scrape_date) FROM ktc_rankings)
GROUP BY position
ORDER BY player_count DESC, position ASC;

-- Average value by position for the latest scrape date.
SELECT position, ROUND(AVG(value), 2) AS avg_value
FROM ktc_rankings
WHERE scrape_date = (SELECT MAX(scrape_date) FROM ktc_rankings)
GROUP BY position
ORDER BY avg_value DESC;

-- Largest movers between the two most recent scrape dates.
WITH recent_dates AS (
    SELECT scrape_date
    FROM ktc_rankings
    GROUP BY scrape_date
    ORDER BY scrape_date DESC
    LIMIT 2
),
ranked AS (
    SELECT
        scrape_date,
        player_name,
        rank_overall,
        ROW_NUMBER() OVER (PARTITION BY player_name ORDER BY scrape_date DESC) AS rn
    FROM ktc_rankings
    WHERE scrape_date IN recent_dates
)
SELECT
    current.player_name,
    previous.rank_overall AS previous_rank,
    current.rank_overall AS current_rank,
    previous.rank_overall - current.rank_overall AS rank_change
FROM ranked AS current
JOIN ranked AS previous
    ON current.player_name = previous.player_name
WHERE current.rn = 1
  AND previous.rn = 2
ORDER BY rank_change DESC, current_rank ASC
LIMIT 15;
