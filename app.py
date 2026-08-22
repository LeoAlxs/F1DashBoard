import streamlit as st
import fastf1
import fastf1.plotting
import os
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# One accent color used consistently anywhere we build custom HTML/CSS,
# so it doesn't get chosen ad-hoc in different places.
ACCENT_COLOR = "#c8ff3d"

# ---- Helper: rotate track X/Y coordinates to FastF1's official orientation ----
# FastF1's raw X/Y telemetry coordinates come out in an arbitrary rotation
# that has nothing to do with how the track "should" look — it depends on
# wherever that circuit's GPS reference point happens to be. FastF1
# separately provides the correct rotation angle for each circuit via
# get_circuit_info().rotation. This function applies that rotation using
# standard 2D rotation math, which is the same approach used in FastF1's
# own official track-map examples.
def rotate_points(x, y, angle_degrees):
    angle = np.deg2rad(angle_degrees)
    x_rotated = x * np.cos(angle) - y * np.sin(angle)
    y_rotated = x * np.sin(angle) + y * np.cos(angle)
    return x_rotated, y_rotated

# ---- Helper: get a team's official F1 color, with a safe fallback ----
# fastf1.plotting.get_team_color() returns a real hex color code used by
# that team (e.g. McLaren orange, Ferrari red). We wrap it in a function
# with a fallback color, in case a team name isn't recognized for some
# older season — this way the app never crashes over a missing color,
# it just falls back to a plain default.
def get_color(team_name, session):
    try:
        return fastf1.plotting.get_team_color(team_name, session=session)
    except Exception:
        return "#636EFA"  # Plotly's default blue

# ---- Helper: apply one consistent look to every chart ----
# Instead of setting font/height/margins separately on each chart (and
# risking them all looking slightly different), every chart passes
# through this one function right before it's displayed. Change
# something here, and it updates everywhere at once.
def style_chart(fig, height=380):
    fig.update_layout(
        height=height,
        margin=dict(l=40, r=20, t=40, b=40),
        font=dict(family="Titillium Web, sans-serif", size=12),
    )
    return fig

# ---- Helper: a colored dot + label for tire compound, instead of plain text ----
# Real F1 broadcasts use consistent colors per tire compound. Adding a
# colored circle in front of the text lets you SCAN the column by color
# instead of reading every single word.
COMPOUND_COLORS = {
    "SOFT": "🔴",
    "MEDIUM": "🟡",
    "HARD": "⚪",
    "INTERMEDIATE": "🟢",
    "WET": "🔵",
}

def compound_label(compound):
    if pd.isna(compound):
        return compound
    dot = COMPOUND_COLORS.get(compound, "")
    return f"{dot} {compound}"

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

# ---- Helper: build a custom HTML lap table with the fastest sector highlighted ----
# Streamlit's built-in st.dataframe is a specialized widget, not regular
# HTML — it doesn't pick up our custom font, and there's no simple way
# to color individual cells based on a condition. Building the table
# ourselves as HTML (via st.markdown) sidesteps both problems: full font
# control, and we can highlight whichever sector was fastest on each lap
# so it's an instant visual read instead of comparing three similar
# numbers.
def build_lap_table_html(laps):
    rows_html = ""
    for _, lap in laps.iterrows():
        # Compare the three RAW (numeric) sector times to find which was
        # fastest this lap — done on numbers, not the formatted text.
        sector_seconds = {
            1: lap["Sector1Seconds"],
            2: lap["Sector2Seconds"],
            3: lap["Sector3Seconds"],
        }
        valid_sectors = {k: v for k, v in sector_seconds.items() if pd.notna(v)}
        fastest_sector = min(valid_sectors, key=valid_sectors.get) if valid_sectors else None

        def sector_cell(sector_num, display_value):
            is_fastest = sector_num == fastest_sector
            style = f"color:{ACCENT_COLOR}; font-weight:600;" if is_fastest else "color:#e0e0e0;"
            return f'<td style="{style} padding:8px 12px;">{display_value or ""}</td>'

        rows_html += f"""
        <tr style="border-bottom:1px solid #262b36;">
            <td style="padding:8px 12px; color:#8a8f98;">{lap['LapNumber']}</td>
            <td style="padding:8px 12px; color:#fff;">{lap['LapTime'] or ''}</td>
            {sector_cell(1, lap['Sector1Time'])}
            {sector_cell(2, lap['Sector2Time'])}
            {sector_cell(3, lap['Sector3Time'])}
            <td style="padding:8px 12px; color:#e0e0e0;">{lap['Compound']}</td>
        </tr>
        """

    return f"""
    <div style="max-height:420px; overflow-y:auto; border:1px solid #262b36; border-radius:8px;">
    <table style="width:100%; border-collapse:collapse; font-family:'Titillium Web', sans-serif; font-size:14px;">
        <thead style="position:sticky; top:0; background:#151b24;">
            <tr style="text-align:left; color:#8a8f98; font-size:12px; text-transform:uppercase; letter-spacing:0.04em;">
                <th style="padding:10px 12px;">Lap</th>
                <th style="padding:10px 12px;">Lap Time</th>
                <th style="padding:10px 12px;">Sector 1</th>
                <th style="padding:10px 12px;">Sector 2</th>
                <th style="padding:10px 12px;">Sector 3</th>
                <th style="padding:10px 12px;">Compound</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
    </div>
    """

# ---- 1. Page setup ----
st.set_page_config(page_title="F1 Dashboard", page_icon="🏁", layout="wide")

# ---- 1b. Custom font ----
# Titillium Web is the actual font used in official F1 broadcast graphics
# and timing screens. Streamlit doesn't let you set a custom font through
# normal Python code — we have to inject a small snippet of raw CSS,
# which is what st.markdown(unsafe_allow_html=True) is for. This imports
# the font from Google Fonts, then tells every heading and normal text
# element on the page to use it.
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Titillium+Web:wght@400;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Titillium Web', sans-serif;
    }
    h1, h2, h3 {
        font-family: 'Titillium Web', sans-serif;
        font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

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
st.title("F1 Race Dashboard")
st.write(f"Showing data for the **{race_name}**, {year} season.")

# ---- 7. Load the selected race ----
with st.spinner("Loading race data..."):
    session = load_race(year, round_number)

# ---- 7b. Track outline (moved to the top) ----
# This is the very first thing shown after the race loads — a quick visual
# of the circuit itself before diving into tables and stats. It's built
# from the OVERALL fastest lap of the race (not a specific driver), so it
# doesn't depend on the driver dropdown further down the page.
#
# get_telemetry() merges car data with position (X/Y) data, unlike
# get_car_data() which we use later for speed/throttle/brake — this is
# the one place we actually need real 2D coordinates instead of just
# "distance along the lap."
overall_fastest_lap = session.laps.pick_fastest()

st.subheader(f"{race_name} — Track Outline")

# Some laps have incomplete or missing position data (a real gap in the
# underlying F1 data, not something we can fix) — get_telemetry() throws
# an error in that case. Without this try/except, that error would crash
# the ENTIRE page, since Streamlit runs the whole script top to bottom.
# Instead, we catch it and just skip this one chart with a friendly note.
try:
    track_telemetry = overall_fastest_lap.get_telemetry()

    # FastF1's raw X/Y coordinates come out in an arbitrary rotation that
    # has nothing to do with the track's real-world orientation.
    # get_circuit_info().rotation gives us the correct angle to rotate by
    # — this is the same value FastF1's own official examples use.
    circuit_info = session.get_circuit_info()
    rotated_x, rotated_y = rotate_points(
        track_telemetry["X"], track_telemetry["Y"], circuit_info.rotation
    )
    track_telemetry = track_telemetry.copy()
    track_telemetry["X"] = rotated_x
    track_telemetry["Y"] = rotated_y

    track_fig = px.line(
        track_telemetry,
        x="X",
        y="Y",
        template="plotly_dark",
    )

    # Color the track line with the team color of whoever set this lap,
    # instead of Plotly's generic default blue.
    track_color = get_color(overall_fastest_lap["Team"], session)
    track_fig.update_traces(line_color=track_color)

    # X and Y are raw position coordinates, not measurements with
    # real-world units someone would read off an axis — hide the
    # numbers/gridlines and just show the shape itself.
    track_fig.update_xaxes(showticklabels=False, showgrid=False, zeroline=False, title=None)
    track_fig.update_yaxes(showticklabels=False, showgrid=False, zeroline=False, title=None)

    # scaleanchor keeps the track's true proportions (1 meter is 1 meter
    # in both directions, so corners aren't stretched into the wrong
    # angle). constrain="domain" is what fixes the "some tracks look
    # tiny" problem — it tells Plotly to shrink whichever axis needs it
    # so the track fills as much of the chart box as it can while still
    # respecting the accurate proportions, instead of leaving the rest
    # of the box empty.
    track_fig.update_yaxes(scaleanchor="x", scaleratio=1, constrain="domain")
    track_fig.update_xaxes(constrain="domain")

    track_fig = style_chart(track_fig, height=450)
    st.plotly_chart(track_fig, use_container_width=True)
except Exception:
    st.info(
        "Track outline isn't available for this race — the underlying "
        "position data is incomplete for this lap."
    )

# ---- 8. Session info ----
# A bigger, bolder header instead of plain text — this is the same
# "small caps label + big title + muted subtitle" pattern used in real
# broadcast graphics, giving the page a clear focal point right under
# the track outline.
st.markdown(
    f"""
    <div style="margin:8px 0 24px 0;">
        <p style="color:{ACCENT_COLOR}; font-size:13px; font-weight:600;
                  letter-spacing:0.08em; text-transform:uppercase; margin:0 0 4px 0;
                  font-family:'Titillium Web', sans-serif;">
            Session Info
        </p>
        <h2 style="font-size:34px; font-weight:700; margin:0 0 4px 0;
                   font-family:'Titillium Web', sans-serif;">
            {session.event['EventName']}
        </h2>
        <p style="color:#8a8f98; font-size:14px; margin:0;
                  font-family:'Titillium Web', sans-serif;">
            {session.event['EventDate']}
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

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

# A second dropdown for comparison, excluding whoever is already selected
# above — comparing a driver against themselves wouldn't be useful.
compare_driver = st.sidebar.selectbox(
    "Compare With",
    [d for d in drivers if d != selected_driver],
)

# pick_driver filters the full lap dataset down to just this driver's laps.
driver_laps = session.laps.pick_driver(selected_driver).copy()

# We save the lap time as a plain number (seconds) BEFORE formatting it as
# display text below. Charts need actual numbers to plot — "1:32.608" is
# just text as far as a chart is concerned, but 92.608 is a number it can
# place on a graph.
driver_laps["LapTimeSeconds"] = driver_laps["LapTime"].dt.total_seconds()

driver_laps["LapTime"] = driver_laps["LapTime"].apply(format_laptime)

# Save the RAW sector times in seconds before formatting, same reasoning
# as LapTimeSeconds above — we need actual numbers to compare which
# sector was fastest, then format the display text separately after.
driver_laps["Sector1Seconds"] = driver_laps["Sector1Time"].dt.total_seconds()
driver_laps["Sector2Seconds"] = driver_laps["Sector2Time"].dt.total_seconds()
driver_laps["Sector3Seconds"] = driver_laps["Sector3Time"].dt.total_seconds()

driver_laps["Sector1Time"] = driver_laps["Sector1Time"].apply(format_laptime)
driver_laps["Sector2Time"] = driver_laps["Sector2Time"].apply(format_laptime)
driver_laps["Sector3Time"] = driver_laps["Sector3Time"].apply(format_laptime)
# Colored dot in front of the compound name, so the eye can scan for
# color instead of reading "HARD" repeated a dozen times in a row.
driver_laps["Compound"] = driver_laps["Compound"].apply(compound_label)

st.subheader(f"{selected_driver}'s Full Race — Lap by Lap")
st.markdown(build_lap_table_html(driver_laps), unsafe_allow_html=True)

# ---- 12b. Lap time progression chart (NEW) ----
# This shows the shape of a driver's whole race at a glance: did they get
# faster as fuel burned off, slower as tires wore out, lose time in
# traffic, or have a dip from a pit stop? A table of numbers can't show
# that pattern nearly as clearly as a line chart can.
st.subheader(f"{selected_driver}'s Pace Across the Race")

# Some laps have no valid time (e.g. the lap right after a pit stop, or a
# lap under a safety car) — we drop those so the chart doesn't show a gap
# dropping to zero.
pace_data = driver_laps.dropna(subset=["LapTimeSeconds"])

pace_fig = px.line(
    pace_data,
    x="LapNumber",
    y="LapTimeSeconds",
    markers=True,  # shows a dot on each individual lap, not just a smooth line
    labels={"LapNumber": "Lap", "LapTimeSeconds": "Lap Time (seconds)"},
    template="plotly_dark",  # matches the dark theme we'll build out fully later
)
driver_color = get_color(driver_laps["Team"].iloc[0], session)
pace_fig.update_traces(line_color=driver_color)
pace_fig = style_chart(pace_fig)
st.plotly_chart(pace_fig, use_container_width=True)

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

# add_distance() calculates how far (in meters) into the lap each telemetry
# reading was taken. This becomes our x-axis below — instead of plotting
# against raw time, we plot against physical position around the track,
# so the chart shape actually reflects the circuit's layout (straights,
# corners, etc.).
telemetry = telemetry.add_distance()

col3, col4, col5, col6 = st.columns(4)
col3.metric("Top Speed", f"{telemetry['Speed'].max():.0f} km/h")
col4.metric("Avg Throttle", f"{telemetry['Throttle'].mean():.0f}%")
col5.metric("Max RPM", f"{telemetry['RPM'].max():.0f}")
col6.metric("Time Braking", f"{telemetry['Brake'].mean() * 100:.0f}%")

# ---- 14. Combined telemetry chart (speed, throttle, brake) ----
# Previously these were three separate full-width charts, each with its
# own x-axis label repeated underneath. That's a lot of scrolling for
# data that's really one connected story — what the car was doing, at
# every point on track, across three different measurements.
#
# make_subplots with shared_xaxes=True stacks three small charts on top
# of each other that all line up on the same horizontal position, so you
# can trace a straight line down through speed/throttle/brake at any
# point on the lap and see all three at once.
st.subheader(f"{selected_driver}'s Fastest Lap — Telemetry")
telemetry_color = get_color(driver_fastest_lap["Team"], session)

telemetry_fig = make_subplots(
    rows=3,
    cols=1,
    shared_xaxes=True,
    subplot_titles=("Speed (km/h)", "Throttle (%)", "Brake"),
    vertical_spacing=0.08,
)

# go.Scatter is the lower-level building block px.line uses internally —
# we need it here since make_subplots needs traces added one at a time,
# rather than one call building the whole figure like px.line does.
telemetry_fig.add_trace(
    go.Scatter(x=telemetry["Distance"], y=telemetry["Speed"], line=dict(color=telemetry_color), showlegend=False),
    row=1, col=1,
)
telemetry_fig.add_trace(
    go.Scatter(x=telemetry["Distance"], y=telemetry["Throttle"], line=dict(color=telemetry_color), showlegend=False),
    row=2, col=1,
)
telemetry_fig.add_trace(
    go.Scatter(x=telemetry["Distance"], y=telemetry["Brake"], line=dict(color=telemetry_color), showlegend=False),
    row=3, col=1,
)

telemetry_fig.update_xaxes(title_text="Distance around lap (m)", row=3, col=1)
telemetry_fig.update_layout(template="plotly_dark")
telemetry_fig = style_chart(telemetry_fig, height=650)
st.plotly_chart(telemetry_fig, use_container_width=True)

# ---- 15. Driver vs. driver comparison (NEW) ----
# This is the section that actually answers "who was faster, and where."
# The trick used throughout this section: build two small tables (one per
# driver) that have the SAME column names, add a "Driver" column to each
# so we know which rows belong to who, then stack them into one combined
# table. Plotly can then draw one separate colored line per driver
# automatically, just by telling it color="Driver".
st.header(f"⚔️ {selected_driver} vs {compare_driver}")

# --- Lap time comparison ---
compare_laps = session.laps.pick_driver(compare_driver).copy()
compare_laps["LapTimeSeconds"] = compare_laps["LapTime"].dt.total_seconds()

driver1_pace = pace_data[["LapNumber", "LapTimeSeconds"]].copy()
driver1_pace["Driver"] = selected_driver

driver2_pace = compare_laps.dropna(subset=["LapTimeSeconds"])[["LapNumber", "LapTimeSeconds"]].copy()
driver2_pace["Driver"] = compare_driver

combined_pace = pd.concat([driver1_pace, driver2_pace])

# Build a color map so each driver's line uses THEIR team's real color,
# instead of Plotly's generic default two-color palette. color_discrete_map
# takes a dictionary of {value in the "color" column: hex color to use}.
compare_color = get_color(compare_laps["Team"].iloc[0], session)
driver_color_map = {selected_driver: driver_color, compare_driver: compare_color}

st.subheader("Lap Time Comparison")
compare_pace_fig = px.line(
    combined_pace,
    x="LapNumber",
    y="LapTimeSeconds",
    color="Driver",
    color_discrete_map=driver_color_map,
    line_dash="Driver",  # gives each driver a different line style (solid vs dashed)
    markers=True,
    labels={"LapNumber": "Lap", "LapTimeSeconds": "Lap Time (seconds)"},
    template="plotly_dark",
)
compare_pace_fig = style_chart(compare_pace_fig)
st.plotly_chart(compare_pace_fig, use_container_width=True)

# --- Speed trace comparison, using each driver's fastest lap ---
compare_fastest_lap = session.laps.pick_driver(compare_driver).pick_fastest()
compare_telemetry = compare_fastest_lap.get_car_data().add_distance()

telemetry_labeled = telemetry[["Distance", "Speed"]].copy()
telemetry_labeled["Driver"] = selected_driver

compare_telemetry_labeled = compare_telemetry[["Distance", "Speed"]].copy()
compare_telemetry_labeled["Driver"] = compare_driver

combined_telemetry = pd.concat([telemetry_labeled, compare_telemetry_labeled])

st.subheader("Fastest Lap — Speed Comparison")
compare_speed_fig = px.line(
    combined_telemetry,
    x="Distance",
    y="Speed",
    color="Driver",
    color_discrete_map=driver_color_map,
    line_dash="Driver",
    labels={"Distance": "Distance around lap (m)", "Speed": "Speed (km/h)"},
    template="plotly_dark",
)
compare_speed_fig = style_chart(compare_speed_fig)
st.plotly_chart(compare_speed_fig, use_container_width=True)