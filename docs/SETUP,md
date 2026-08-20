# Setup Guide

This guide walks through everything needed to run the F1 Dashboard on your own computer, assuming no prior setup.

## 1. Install Python

You need Python 3.9 or newer.

- Go to [python.org/downloads](https://www.python.org/downloads/)
- Download and run the installer for your operating system
- **Windows users:** on the first screen of the installer, check the box that says "Add Python to PATH" before clicking Install — this lets you run Python from any terminal.
- To confirm it worked, open a terminal (Command Prompt, PowerShell, or Terminal on Mac) and run:
  ```bash
  python --version
  ```
  You should see something like `Python 3.11.x`.

## 2. Install Git

Git is needed to download (clone) this project.

- Go to [git-scm.com/downloads](https://git-scm.com/downloads)
- Download and run the installer, keeping the default options
- Confirm it worked:
  ```bash
  git --version
  ```

## 3. Clone the project

In a terminal, navigate to wherever you want the project folder to live, then run:

```bash
git clone https://github.com/LeoAlxs/F1DashBoard.git
cd F1DashBoard
```

This downloads a full copy of the project and moves you into its folder.

## 4. (Recommended) Create a virtual environment

A virtual environment keeps this project's Python libraries separate from other projects on your computer, avoiding version conflicts.

```bash
python -m venv venv
```

Then activate it:

- **Windows:**
  ```bash
  venv\Scripts\activate
  ```
- **Mac/Linux:**
  ```bash
  source venv/bin/activate
  ```

You'll know it worked if you see `(venv)` appear at the start of your terminal line. You'll need to run the activate command again each time you reopen a terminal for this project.

## 5. Install the required libraries

With your virtual environment active, run:

```bash
pip install -r requirements.txt
```

This reads the `requirements.txt` file in the project and installs every library listed there (Streamlit, FastF1, pandas, Plotly, matplotlib) automatically — no need to install them one by one.

## 6. Run the app

```bash
streamlit run app.py
```

This starts a local web server and should automatically open the dashboard in your default browser at `http://localhost:8501`. If it doesn't open automatically, copy that address into your browser manually.

## 7. Using the dashboard

- Use the sidebar to pick a season and race
- Pick a driver to see their full race breakdown and telemetry
- Pick a second driver under "Compare With" to see a head-to-head comparison

## Troubleshooting

**"streamlit: command not found" or similar**
Your virtual environment probably isn't active — repeat step 4's activate command, then try again.

**First race you select takes a while to load**
This is normal — FastF1 is downloading that race's data for the first time. It gets cached locally, so loading the same race again later will be instant.

**"pip: command not found"**
Try `pip3` instead of `pip`, or reinstall Python and make sure it was added to PATH (see step 1).