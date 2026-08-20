import streamlit as st
import fastf1
import os
import pandas as pd

# ---- Helper: format a lap time (timedelta) as clean text like "1:32.608" ----
# Without this, Streamlit's table widget tries to "smartly" format durations
# and rounds them to something vague like "2 minutes". Converting to a plain
# string ourselves guarantees the exact value is shown.
def format_laptime(td):
    if pd.isna(td):
        return None
    total_seconds = td.total_seconds()
    minutes = int(total_seconds // 60)
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:06.3f}"

# ---- 1. Page setup ----
st.set_page_config(page_title="F1 Dashboard", page_icon="🏁", layout="wide")

# ---- 2. Cache setup ----
CACHE_DIR = "f1_cache"
os.makedirs(CACHE_DIR, exist_ok=True)
fastf1.Cache.enable_cache(CACHE_DIR)

# ---- 3. Load the full race calendar for a season ----
# Instead of hardcoding race names, we ask FastF1 for the real schedule.
# We cache this too, since the schedule doesn't change moment to moment.
@st.cache_data
def load_schedule(year):
    schedule = fastf1.get_event_schedule(year)
    # Drop pre-season testing events — we only want actual races.
    races = schedule[schedule["EventFormat"] != "testing"]
    return races

# ---- 4. Load one race session ----
# We use the round NUMBER (1st race, 2nd race, etc.) instead of the race
# name string. Names can be inconsistent ("Bahrain" vs "Bahrain Grand
# Prix"), but round numbers are always reliable.
@st.cache_data
def load_race(year, round_number):
    session = fastf1.get_session(year, round_number, "R")
    session.load()
    return session

# ---- 5. Sidebar: season + race picker, built from real data ----
st.sidebar.title("Select a Race")
# Newest season first, since that's usually what people want to see.
year = st.sidebar.selectbox("Season", [2026, 2025, 2024])

schedule = load_schedule(year)

# If we're looking at the CURRENT season, some races on the calendar
# haven't happened yet — they exist in the schedule but have no data.
# We filter those out so the dropdown only ever shows races we can
# actually load, instead of letting the user pick a future race and hit
# an error.
today = pd.Timestamp.now()
schedule = schedule[schedule["EventDate"] <= today]

# Build a lookup so we can show race NAMES in the dropdown but still
# know each race's ROUND NUMBER underneath (needed for step 4 above).
race_name_to_round = dict(zip(schedule["EventName"], schedule["RoundNumber"]))
race_name = st.sidebar.selectbox("Race", list(race_name_to_round.keys()))
round_number = race_name_to_round[race_name]

# ---- 6. Main title ----
st.title("🏁 F1 Race Dashboard")
st.write(f"Showing data for the **{race_name}**, {year} season.")

# ---- 7. Load the selected race ----
with st.spinner("Loading race data..."):
    session = load_race(year, round_number)

# ---- 8. Session info ----
st.subheader("Session Info")
st.write(f"**Event:** {session.event['EventName']}")
st.write(f"**Date:** {session.event['EventDate']}")

# ---- 9. Race results table (NEW) ----
# session.results holds the official classification: who finished where,
# for which team, and how many points they scored.
st.subheader("Race Results (Top 10)")
results = session.results[["Position", "Abbreviation", "TeamName", "Points"]].head(10)
st.dataframe(results, use_container_width=True)

# ---- 10. Fastest lap ----
st.subheader("Fastest Lap")
fastest_lap = session.laps.pick_fastest()
col1, col2 = st.columns(2)
col1.metric("Driver", fastest_lap["Driver"])
col2.metric("Lap Time", format_laptime(fastest_lap["LapTime"]))

# ---- 11. Top 5 fastest laps ----
st.subheader("Top 5 Fastest Laps")
top_5 = session.laps.sort_values("LapTime").head(5).copy()
# .copy() avoids a pandas warning since we're about to modify this slice
top_5["LapTime"] = top_5["LapTime"].apply(format_laptime)
st.dataframe(
    top_5[["Driver", "LapTime", "LapNumber"]],
    use_container_width=True,
    hide_index=True,  # hides the leftover row-position numbers
)

# ---- 12. Driver-specific lap breakdown (NEW) ----
# A second sidebar control, separate from the race picker, letting the
# user drill into one specific driver's full race.
st.sidebar.subheader("Compare a Driver")
drivers = sorted(session.laps["Driver"].unique())
selected_driver = st.sidebar.selectbox("Driver", drivers)

# pick_driver filters the full lap dataset down to just this driver's laps.
driver_laps = session.laps.pick_driver(selected_driver).copy()
driver_laps["LapTime"] = driver_laps["LapTime"].apply(format_laptime)
# Sector times are also timedeltas, so we format them the same way.
driver_laps["Sector1Time"] = driver_laps["Sector1Time"].apply(format_laptime)
driver_laps["Sector2Time"] = driver_laps["Sector2Time"].apply(format_laptime)
driver_laps["Sector3Time"] = driver_laps["Sector3Time"].apply(format_laptime)

st.subheader(f"{selected_driver}'s Full Race — Lap by Lap")
st.dataframe(
    driver_laps[
        ["LapNumber", "LapTime", "Sector1Time", "Sector2Time", "Sector3Time", "Compound"]
    ],
    use_container_width=True,
    hide_index=True,
)

# ---- 13. Telemetry summary for the fastest lap (NEW) ----
# Telemetry is much more detailed than lap data — hundreds of individual
# readings taken throughout a single lap (speed, throttle, brake, gear,
# track position). Rather than dump hundreds of rows on the page, we pull
# it for the driver's fastest lap and show a few clean summary numbers.
# This same telemetry data is what we'll plot as an actual line chart
# (speed/throttle/brake vs distance) in the next phase.
st.subheader(f"{selected_driver}'s Fastest Lap — Telemetry Summary")

driver_fastest_lap = session.laps.pick_driver(selected_driver).pick_fastest()
telemetry = driver_fastest_lap.get_car_data()

col3, col4, col5 = st.columns(3)
col3.metric("Top Speed", f"{telemetry['Speed'].max():.0f} km/h")
col4.metric("Avg Throttle", f"{telemetry['Throttle'].mean():.0f}%")
col5.metric("Max RPM", f"{telemetry['RPM'].max():.0f}")