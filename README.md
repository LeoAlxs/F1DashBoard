# F1 Race Dashboard

An interactive Formula 1 data dashboard built with Streamlit and FastF1. Select any race from the 2024-2026 seasons to explore race results, lap times, sector splits, and telemetry, including head-to-head comparisons between two drivers.

## Features

- Dynamic race calendar for the 2024, 2025, and 2026 seasons, with races that have not yet taken place automatically filtered out
- Race results, fastest lap, and top 5 fastest laps
- Full lap-by-lap breakdown per driver, including sector times and tire compound
- Lap time progression chart showing how a driver's pace changed across the race
- Speed and throttle telemetry traces for a driver's fastest lap
- Head-to-head driver comparison, with lap times and speed traces overlaid for two drivers

## Built With

- Streamlit - turns the Python script into an interactive web app
- FastF1 - official F1 timing and telemetry data
- Plotly - interactive charts
- pandas - data handling

## Quick Start

Full step-by-step instructions, including installing Python and Git if not already installed, are available in [docs/SETUP.md](docs/SETUP.md).

If Python and Git are already installed:

```bash
git clone https://github.com/LeoAlxs/F1DashBoard.git
cd F1DashBoard
pip install -r requirements.txt
streamlit run app.py
```

## Data Source

All race data is pulled from official F1 timing feeds via the FastF1 Python library. Data is cached locally after the first fetch.

## License

This project was built as a demo and portfolio project. F1 data is provided courtesy of the FastF1 library and is not affiliated with Formula 1 or the FIA.
