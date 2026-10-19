import os

import requests
import streamlit as st

BASE_URL = os.getenv("KTC_API_URL", "http://localhost:8000")
REQUEST_TIMEOUT_SECONDS = 10


def fetch(path: str, params: dict | None = None):
    """GET a JSON payload from the API, stopping the page with a readable error on failure."""

    try:
        response = requests.get(f"{BASE_URL}{path}", params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        st.error(f"Could not reach the API at {BASE_URL}: {exc}")
        st.stop()
    if response.status_code != 200:
        detail = response.json().get("detail", response.text) if response.content else ""
        st.error(f"API error {response.status_code}: {detail}")
        st.stop()
    return response.json()


st.set_page_config(page_title="KTC Dynasty Rankings", layout="wide")
st.title("🏈 KTC Dynasty Rankings Dashboard")

# Search bar for a player's history across snapshots
name_query = st.text_input("Search by Player Name", "")

if name_query:
    players = fetch("/player", {"name": name_query})
    if players:
        st.subheader(f"Ranking history for '{name_query}'")
        st.dataframe(players)
    else:
        st.warning("No players found.")

st.markdown("---")

# Filters in sidebar
st.sidebar.header("🔍 Filters")
scrape_dates = fetch("/scrape-dates")
scrape_date = st.sidebar.selectbox("Snapshot date", scrape_dates)
position = st.sidebar.selectbox("Position", ["", "QB", "RB", "WR", "TE", "PICK"])
team = st.sidebar.text_input("Team")
tier = st.sidebar.number_input(
    "Tier",
    min_value=0,
    max_value=15,
    step=1,
    format="%d",
    key="tier",
    help="Optional filter for tier (0 shows all tiers).",
)
page = st.sidebar.number_input(
    "Page",
    min_value=1,
    value=1,
    step=1,
    key="page",
    help="Optional filter for pagination.",
)
limit = st.sidebar.slider("Results per Page", min_value=10, max_value=50, value=25)

params = {"page": page, "limit": limit}
if scrape_date:
    params["scrape_date"] = scrape_date
if position:
    params["position"] = position
if team:
    params["team"] = team
if tier:
    params["tier"] = tier

st.subheader(f"📊 Player Rankings ({scrape_date or 'no snapshots yet'})")
data = fetch("/rankings", params)
if data:
    st.dataframe(data)
else:
    st.info("No results match your filters.")
