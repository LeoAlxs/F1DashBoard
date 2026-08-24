import streamlit as st
import fastf1
import fastf1.plotting
import os
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ACCENT_COLOR = "#c8ff3d"

# Rotates track X/Y coordinates to FastF1's official circuit orientation.
def rotate_points(x, y, angle_degrees):
    angle = np.deg2rad(angle_degrees)
    x_rotated = x * np.cos(angle) - y * np.sin(angle)
    y_rotated = x * np.sin(angle) + y * np.cos(angle)
    return x_rotated, y_rotated

# Gets a team's official color, with a safe fallback if not found.
def get_color(team_name, session):
    try:
        return fastf1.plotting.get_team_color(team_name, session=session)
    except Exception:
        return "#636EFA"

# Picks black or white text for readable contrast against a given color.
def get_contrast_text_color(hex_color):
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    brightness = (r * 299 + g * 587 + b * 114) / 1000
    return "#000000" if brightness > 150 else "#ffffff"

# Converts a hex color into a semi-transparent rgba string.
def hex_to_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

# Scales a set of points outward from their own centroid (for the track's echo effect).
def scale_points_from_centroid(x, y, scale_factor):
    centroid_x = x.mean()
    centroid_y = y.mean()
    scaled_x = centroid_x + (x - centroid_x) * scale_factor
    scaled_y = centroid_y + (y - centroid_y) * scale_factor
    return scaled_x, scaled_y

# Applies consistent height/margin/font styling to every chart.
def style_chart(fig, height=380):
    fig.update_layout(
        height=height,
        margin=dict(l=40, r=20, t=40, b=40),
        font=dict(family="Titillium Web, sans-serif", size=12),
    )
    return fig

# Colored dot per tire compound, so the compound column can be scanned by color.
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

# Formats a lap time as clean text (e.g. "1:32.608") instead of Streamlit's default rounding.
def format_laptime(td):
    if pd.isna(td):
        return None
    total_seconds = td.total_seconds()
    minutes = int(total_seconds // 60)
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:06.3f}"

# Renders a big styled section header (small accent label + large title).
# Built as flat, unindented HTML strings — indented lines get treated as a markdown code block.
def section_header(label, title, subtitle=None, font="Orbitron"):
    subtitle_html = f'<p style="color:#8a8f98; font-size:14px; margin:0; font-family:\'Titillium Web\', sans-serif;">{subtitle}</p>' if subtitle else ""
    html = (
        f'<div style="margin:4px 0 20px 0;">'
        f'<p style="color:{ACCENT_COLOR}; font-size:13px; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; margin:0 0 4px 0; font-family:\'Titillium Web\', sans-serif;">{label}</p>'
        f'<h2 style="font-size:30px; font-weight:800; margin:0 0 4px 0; font-family:\'{font}\', sans-serif;">{title}</h2>'
        f'{subtitle_html}'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)

# Builds the lap-by-lap table as custom HTML, highlighting each lap's fastest sector.
def build_lap_table_html(laps):
    row_strings = []
    for _, lap in laps.iterrows():
        sector_seconds = {
            1: lap["Sector1Seconds"],
            2: lap["Sector2Seconds"],
            3: lap["Sector3Seconds"],
        }
        valid_sectors = {k: v for k, v in sector_seconds.items() if pd.notna(v)}
        fastest_sector = min(valid_sectors, key=valid_sectors.get) if valid_sectors else None

        def sector_cell(sector_num, display_value):
            is_fastest = sector_num == fastest_sector
            style = f"color:{ACCENT_COLOR};font-weight:600;" if is_fastest else "color:#e0e0e0;"
            return f'<td style="{style}padding:8px 12px;">{display_value or ""}</td>'

        row = (
            '<tr style="border-bottom:1px solid #262b36;">'
            f'<td style="padding:8px 12px;color:#8a8f98;">{lap["LapNumber"]}</td>'
            f'<td style="padding:8px 12px;color:#fff;">{lap["LapTime"] or ""}</td>'
            f'{sector_cell(1, lap["Sector1Time"])}'
            f'{sector_cell(2, lap["Sector2Time"])}'
            f'{sector_cell(3, lap["Sector3Time"])}'
            f'<td style="padding:8px 12px;color:#e0e0e0;">{lap["Compound"]}</td>'
            '</tr>'
        )
        row_strings.append(row)

    rows_html = "".join(row_strings)

    table_html = (
        '<div style="max-height:420px;overflow-y:auto;border:1px solid #262b36;border-radius:8px;">'
        '<table style="width:100%;border-collapse:collapse;font-family:\'Titillium Web\', sans-serif;font-size:14px;">'
        '<thead style="position:sticky;top:0;background:#151b24;">'
        '<tr style="text-align:left;color:#8a8f98;font-size:12px;text-transform:uppercase;letter-spacing:0.04em;">'
        '<th style="padding:10px 12px;">Lap</th>'
        '<th style="padding:10px 12px;">Lap Time</th>'
        '<th style="padding:10px 12px;">Sector 1</th>'
        '<th style="padding:10px 12px;">Sector 2</th>'
        '<th style="padding:10px 12px;">Sector 3</th>'
        '<th style="padding:10px 12px;">Compound</th>'
        '</tr>'
        '</thead>'
        f'<tbody>{rows_html}</tbody>'
        '</table>'
        '</div>'
    )
    return table_html

# Builds a generic styled HTML table, reused for Race Results and Top 5 Fastest Laps.
def build_generic_table_html(df, columns):
    header_cells = "".join(f'<th style="padding:10px 12px;">{col}</th>' for col in columns)

    row_strings = []
    for _, row in df.iterrows():
        cells = "".join(
            f'<td style="padding:8px 12px;color:#e0e0e0;">{row[col]}</td>' for col in columns
        )
        row_strings.append(f'<tr style="border-bottom:1px solid #262b36;">{cells}</tr>')
    rows_html = "".join(row_strings)

    table_html = (
        '<div style="max-height:420px;overflow-y:auto;border:1px solid #262b36;border-radius:8px;">'
        '<table style="width:100%;border-collapse:collapse;font-family:\'Titillium Web\', sans-serif;font-size:14px;">'
        '<thead style="position:sticky;top:0;background:#151b24;">'
        f'<tr style="text-align:left;color:#8a8f98;font-size:12px;text-transform:uppercase;letter-spacing:0.04em;">{header_cells}</tr>'
        '</thead>'
        f'<tbody>{rows_html}</tbody>'
        '</table>'
        '</div>'
    )
    return table_html

# ---- Page setup ----
st.set_page_config(page_title="F1 Dashboard", page_icon="🏁", layout="wide")

# Injects custom fonts (Titillium Web for body, Orbitron for headings).
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Titillium+Web:wght@400;600;700&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Racing+Sans+One&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Titillium Web', sans-serif;
    }
    h1, h2 {
        font-family: 'Orbitron', sans-serif;
        font-weight: 800;
    }
    h3 {
        font-family: 'Titillium Web', sans-serif;
        font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---- Cache setup ----
CACHE_DIR = "f1_cache"
os.makedirs(CACHE_DIR, exist_ok=True)
fastf1.Cache.enable_cache(CACHE_DIR)

# Loads the season's race calendar, filtering out pre-season testing events.
@st.cache_data
def load_schedule(year):
    schedule = fastf1.get_event_schedule(year)
    races = schedule[schedule["EventFormat"] != "testing"]
    return races

# Loads one race session by round number (more reliable than matching race names).
# Uses cache_resource (not cache_data) since a FastF1 Session is a live object,
# not plain data — cache_data copies/serializes results, which can silently
# strip its internal loaded state; cache_resource caches it by reference instead.
@st.cache_resource
def load_race(year, round_number):
    session = fastf1.get_session(year, round_number, "R")
    session.load()
    return session

# ---- Sidebar: season + race picker ----
st.sidebar.title("Select a Race")
year = st.sidebar.selectbox("Season", [2026, 2025, 2024])

schedule = load_schedule(year)

# Filters out races that haven't happened yet in the current season.
today = pd.Timestamp.now()
schedule = schedule[schedule["EventDate"] <= today]

race_name_to_round = dict(zip(schedule["EventName"], schedule["RoundNumber"]))
race_name = st.sidebar.selectbox("Race", list(race_name_to_round.keys()))
round_number = race_name_to_round[race_name]

# ---- Main title ----
st.title("F1 Race Dashboard")
st.write(f"Showing data for the **{race_name}**, {year} season.")

# ---- Load the selected race ----
with st.spinner("Loading race data..."):
    session = load_race(year, round_number)

# Determines the race winner (Position 1), used for both the track chart and sidebar theming.
winner_rows = session.results[session.results["Position"] == 1]
if not winner_rows.empty:
    winner_abbr = winner_rows.iloc[0]["Abbreviation"]
    winner_team = winner_rows.iloc[0]["TeamName"]
else:
    fallback_lap = session.laps.pick_fastest()
    winner_abbr = fallback_lap["Driver"]
    winner_team = fallback_lap["Team"]

winner_color = get_color(winner_team, session)
winner_text_color = get_contrast_text_color(winner_color)

# Themes the sidebar background/text with the winner's team color.
# Dropdown boxes keep fixed white text since their own background stays dark navy regardless.
st.markdown(
    f"""
    <style>
    [data-testid="stSidebar"] {{
        background-color: {winner_color} !important;
        transition: background-color 0.6s ease;
    }}
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {{
        color: {winner_text_color} !important;
        transition: color 0.6s ease;
    }}
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] p {{
        font-family: 'Titillium Web', sans-serif !important;
    }}
    [data-testid="stSidebar"] h1 {{
        font-family: 'Orbitron', sans-serif !important;
        font-size: 30px !important;
        font-weight: 800 !important;
    }}
    [data-testid="stSidebar"] h3 {{
        font-family: 'Orbitron', sans-serif !important;
        font-size: 22px !important;
        font-weight: 800 !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---- Track outline ----
with st.container(border=True):
    section_header("Circuit", f"{race_name} — Track Outline")

    # Some laps have incomplete position data — caught here so it doesn't crash the whole page.
    try:
        winner_lap = session.laps.pick_driver(winner_abbr).pick_fastest()
        track_telemetry = winner_lap.get_telemetry()

        circuit_info = session.get_circuit_info()
        rotated_x, rotated_y = rotate_points(
            track_telemetry["X"], track_telemetry["Y"], circuit_info.rotation
        )

        # spline smoothing avoids a jagged look between sampled telemetry points.
        line_shape_settings = dict(shape="spline", smoothing=1.0)

        # Each echo layer is a scaled-up copy of the track, fading out with distance.
        echo_layers = [
            (1.32, 0.05),
            (1.25, 0.08),
            (1.18, 0.12),
            (1.11, 0.18),
            (1.05, 0.28),
        ]

        track_fig = go.Figure()
        for scale, alpha in echo_layers:
            echo_x, echo_y = scale_points_from_centroid(rotated_x, rotated_y, scale)
            track_fig.add_trace(go.Scatter(
                x=echo_x, y=echo_y, mode="lines",
                line=dict(color=hex_to_rgba(winner_color, alpha), width=3, **line_shape_settings),
                showlegend=False,
            ))
        # The real, unscaled track outline, drawn last so it's on top and fully opaque.
        track_fig.add_trace(go.Scatter(
            x=rotated_x, y=rotated_y, mode="lines",
            line=dict(color=winner_color, width=3, **line_shape_settings), showlegend=False,
        ))
        track_fig.update_layout(template="plotly_dark")

        track_fig.update_xaxes(showticklabels=False, showgrid=False, zeroline=False, title=None)
        track_fig.update_yaxes(showticklabels=False, showgrid=False, zeroline=False, title=None)

        # Padding prevents the thick outline/echoes from being clipped at the chart edge.
        x_min, x_max = rotated_x.min(), rotated_x.max()
        y_min, y_max = rotated_y.min(), rotated_y.max()
        x_pad = (x_max - x_min) * 0.38
        y_pad = (y_max - y_min) * 0.38

        track_fig.update_xaxes(range=[x_min - x_pad, x_max + x_pad], constrain="domain")
        track_fig.update_yaxes(
            range=[y_min - y_pad, y_max + y_pad],
            scaleanchor="x", scaleratio=1, constrain="domain",
        )

        track_fig = style_chart(track_fig, height=520)
        st.plotly_chart(track_fig, use_container_width=True)
    except Exception:
        st.info(
            "Track outline isn't available for this race — the underlying "
            "position data is incomplete for this lap."
        )

st.divider()

# ---- Session info + race results ----
with st.container(border=True):
    section_header("Session Info", session.event["EventName"], str(session.event["EventDate"]))

    section_header("Standings", "Race Results (Top 10)")
    results = session.results[["Position", "Abbreviation", "TeamName", "Points"]].head(10)
    st.markdown(build_generic_table_html(results, ["Position", "Abbreviation", "TeamName", "Points"]), unsafe_allow_html=True)

st.divider()

# ---- Fastest lap + Top 5 ----
with st.container(border=True):
    section_header("Race Highlights", "Fastest Lap & Top 5")

    fastest_lap = session.laps.pick_fastest()
    col1, col2 = st.columns(2)
    col1.metric("Driver", fastest_lap["Driver"])
    col2.metric("Lap Time", format_laptime(fastest_lap["LapTime"]))

    st.subheader("Top 5 Fastest Laps")
    top_5 = session.laps.sort_values("LapTime").head(5).copy()
    top_5["LapTime"] = top_5["LapTime"].apply(format_laptime)
    st.markdown(build_generic_table_html(top_5, ["Driver", "LapTime", "LapNumber"]), unsafe_allow_html=True)

st.divider()

# ---- Driver-specific breakdown ----
st.sidebar.subheader("Compare a Driver")
drivers = sorted(session.laps["Driver"].unique())
selected_driver = st.sidebar.selectbox("Driver", drivers)

compare_driver = st.sidebar.selectbox(
    "Compare With",
    [d for d in drivers if d != selected_driver],
)

with st.container(border=True):
    section_header("Driver Detail", f"{selected_driver}'s Race")

    driver_laps = session.laps.pick_driver(selected_driver).copy()

    # Raw seconds are kept alongside the formatted display text, since charts need real numbers.
    driver_laps["LapTimeSeconds"] = driver_laps["LapTime"].dt.total_seconds()
    driver_laps["LapTime"] = driver_laps["LapTime"].apply(format_laptime)

    driver_laps["Sector1Seconds"] = driver_laps["Sector1Time"].dt.total_seconds()
    driver_laps["Sector2Seconds"] = driver_laps["Sector2Time"].dt.total_seconds()
    driver_laps["Sector3Seconds"] = driver_laps["Sector3Time"].dt.total_seconds()

    driver_laps["Sector1Time"] = driver_laps["Sector1Time"].apply(format_laptime)
    driver_laps["Sector2Time"] = driver_laps["Sector2Time"].apply(format_laptime)
    driver_laps["Sector3Time"] = driver_laps["Sector3Time"].apply(format_laptime)
    driver_laps["Compound"] = driver_laps["Compound"].apply(compound_label)

    st.subheader("Full Race — Lap by Lap")
    st.markdown(build_lap_table_html(driver_laps), unsafe_allow_html=True)

    # ---- Lap time progression chart ----
    st.subheader("Pace Across the Race")

    pace_data = driver_laps.dropna(subset=["LapTimeSeconds"])

    pace_fig = px.line(
        pace_data,
        x="LapNumber",
        y="LapTimeSeconds",
        markers=True,
        labels={"LapNumber": "Lap", "LapTimeSeconds": "Lap Time (seconds)"},
        template="plotly_dark",
    )
    driver_color = get_color(driver_laps["Team"].iloc[0], session)
    pace_fig.update_traces(line_color=driver_color)
    pace_fig = style_chart(pace_fig)
    st.plotly_chart(pace_fig, use_container_width=True)

    # ---- Telemetry summary for the fastest lap ----
    st.subheader("Fastest Lap — Telemetry")

    driver_fastest_lap = session.laps.pick_driver(selected_driver).pick_fastest()
    telemetry = driver_fastest_lap.get_car_data()
    telemetry = telemetry.add_distance()

    col3, col4, col5, col6 = st.columns(4)
    col3.metric("Top Speed", f"{telemetry['Speed'].max():.0f} km/h")
    col4.metric("Avg Throttle", f"{telemetry['Throttle'].mean():.0f}%")
    col5.metric("Max RPM", f"{telemetry['RPM'].max():.0f}")
    col6.metric("Time Braking", f"{telemetry['Brake'].mean() * 100:.0f}%")

    # ---- Combined telemetry chart (speed, throttle, brake) ----
    telemetry_color = get_color(driver_fastest_lap["Team"], session)

    telemetry_fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        subplot_titles=("Speed (km/h)", "Throttle (%)", "Brake"),
        vertical_spacing=0.08,
    )

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

st.divider()

# ---- Driver vs. driver comparison ----
with st.container(border=True):
    section_header("Head to Head", f"{selected_driver} vs {compare_driver}")

    # --- Lap time comparison ---
    compare_laps = session.laps.pick_driver(compare_driver).copy()
    compare_laps["LapTimeSeconds"] = compare_laps["LapTime"].dt.total_seconds()

    driver1_pace = pace_data[["LapNumber", "LapTimeSeconds"]].copy()
    driver1_pace["Driver"] = selected_driver

    driver2_pace = compare_laps.dropna(subset=["LapTimeSeconds"])[["LapNumber", "LapTimeSeconds"]].copy()
    driver2_pace["Driver"] = compare_driver

    combined_pace = pd.concat([driver1_pace, driver2_pace])

    # Maps each driver to their real team color instead of Plotly's default palette.
    compare_color = get_color(compare_laps["Team"].iloc[0], session)
    driver_color_map = {selected_driver: driver_color, compare_driver: compare_color}

    section_header("Pace", "Lap Time Comparison")
    compare_pace_fig = px.line(
        combined_pace,
        x="LapNumber",
        y="LapTimeSeconds",
        color="Driver",
        color_discrete_map=driver_color_map,
        line_dash="Driver",
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

    section_header("Speed", "Fastest Lap — Speed Comparison")
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