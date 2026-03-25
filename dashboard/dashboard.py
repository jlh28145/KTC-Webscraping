import requests
import streamlit as st

BASE_URL = "http://localhost:8000"

st.set_page_config(page_title="KTC Dynasty Rankings", layout="wide")
st.title("🏈 KTC Dynasty Rankings Dashboard")

# Search bar for player
name_query = st.text_input("Search by Player Name", "")

if name_query:
    res = requests.get(f"{BASE_URL}/player", params={"name": name_query})
    if res.status_code == 200:
        players = res.json()
        if players:
            st.subheader(f"Search Results for '{name_query}'")
            st.table(players)
        else:
            st.warning("No players found.")
    else:
        st.error("API error occurred.")

st.markdown("---")

# Filters in sidebar
st.sidebar.header("🔍 Filters")
position = st.sidebar.selectbox("Position", ["", "QB", "RB", "WR", "TE"])
team = st.sidebar.text_input("Team")
tier = st.sidebar.number_input(
    "Tier",
    min_value=0,
    max_value=15,
    step=1,
    format="%d",
    key="tier",
    help="Optional filter for tier.",
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

# Build parameters for API call
params = {"page": page, "limit": limit}

if position:
    params["position"] = position
if team:
    params["team"] = team
if tier:
    params["tier"] = tier

# Send the request to the API with filters
res = requests.get(f"{BASE_URL}/rankings", params=params)

if res.status_code == 200:
    st.subheader("📊 Player Rankings")
    data = res.json()
    if data:
        st.dataframe(data)
    else:
        st.info("No results match your filters.")
else:
    st.error("Failed to fetch rankings.")
