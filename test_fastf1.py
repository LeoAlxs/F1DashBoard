"""
Quick test script — confirms FastF1 can pull real race data.
Run this BEFORE touching Streamlit or any UI code.

What this does:
1. Sets up a local cache folder (so FastF1 doesn't re-download data every time)
2. Loads one real race session
3. Prints a few basic facts to prove the data pull actually worked
"""

import fastf1

# 1. Set up caching — FastF1 downloads race data from F1's official feeds,
# and caching means it only downloads once, then reuses the local copy.
CACHE_DIR = "f1_cache"

import os
os.makedirs(CACHE_DIR, exist_ok=True)
fastf1.Cache.enable_cache(CACHE_DIR)

# 2. Load a specific race session.
# Using a past, fully-completed race (2024 Bahrain GP) because it's
# guaranteed to have complete data — good for testing.
# 'R' means the Race session (as opposed to Qualifying, Practice, etc.)
print("Loading session data... (first run will download and may take a minute)")
session = fastf1.get_session(2024, "Bahrain", "R")
session.load()

# 3. Print some basic facts to prove it worked.
print("\n--- SESSION INFO ---")
print(f"Event: {session.event['EventName']}")
print(f"Date: {session.event['EventDate']}")

print("\n--- FASTEST LAP OVERALL ---")
fastest_lap = session.laps.pick_fastest()
print(f"Driver: {fastest_lap['Driver']}")
print(f"Lap Time: {fastest_lap['LapTime']}")

print("\n--- TOP 5 FASTEST LAPS ---")
top_5 = session.laps.sort_values("LapTime").head(5)
print(top_5[["Driver", "LapTime", "LapNumber"]].to_string(index=False))

print("\n If you see real driver names and lap times above, FastF1 is working correctly.")
