# PayFlow

PayFlow is a small, beginner-friendly payment reconciliation dashboard. It compares **simulated** merchant and payment-provider transaction exports. It does not send, accept, or process real payments.

## What it does

- Creates accounts and signs users in with securely hashed passwords.
- Stores each user's reconciliation history and report rows in a backend SQLite database.
- Uploads two CSV files: one merchant export and one payment-provider export.
- Matches records by `transaction_id`.
- Flags missing transactions, duplicate IDs, amount mismatches, and currency mismatches.
- Shows summary cards plus a searchable and filterable result table.
- Exports a reconciliation CSV report.
- Includes sample data and automated tests.

## Quick start

1. Install [Python 3.10 or newer](https://www.python.org/downloads/).
2. Open this folder in a terminal.
3. Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

4. Install the packages and start the dashboard:

```powershell
pip install -r requirements.txt
python app.py
```

5. Visit `http://127.0.0.1:5000` in your browser. Create an account, then the dashboard displays the supplied sample reconciliation.

To stop the server, press `Ctrl+C`. On macOS/Linux, activate the virtual environment with `source .venv/bin/activate`.

## CSV format

Both files must be UTF-8 `.csv` files with this header:

```csv
transaction_id,amount,currency,date
TXN-1001,49.99,USD,2026-09-15
```

Try the files in `sample_data/`. They deliberately contain a duplicate ID, a missing merchant transaction, and an amount mismatch so you can see the review states.

## Run tests

With the virtual environment activated:

```powershell
python -m unittest discover -s tests -v
```

## Keep it online (Render deployment)

To keep PayFlow available after you close VS Code, deploy it to Render. The included `render.yaml` tells Render how to install and start the app securely.

1. Create a new GitHub repository and upload this project to it.
2. Create a Render account at https://render.com.
3. In Render, click **New → Blueprint** and connect your GitHub repository.
4. Render detects `render.yaml`. Confirm the blueprint and click **Apply**.
5. After the build completes, open the generated `https://payflow-dashboard.onrender.com` address (Render may add a suffix if that name is taken).

For a persistent backend database, select a paid Render web service: the supplied configuration attaches a persistent disk and writes the SQLite database there. Free Render web services do not support persistent disks, so their local files are erased when the service restarts. For a long-term production app, use a managed PostgreSQL database instead. Do not use the public demo with real transaction data.

## VS Code setup

1. Install VS Code and the **Python** extension by Microsoft.
2. Use **File → Open Folder** and select this PayFlow folder.
3. Press `Ctrl+Shift+P`, choose **Python: Select Interpreter**, then select `.venv`.
4. In the integrated terminal, activate `.venv` and run `python app.py`.
5. To run tests, open the Testing flask icon in the left sidebar or use the test command above.

## Project layout

```text
app.py                 Flask routes, upload validation, and CSV download
reconciliation.py      Matching and reconciliation rules (uses NumPy for totals)
templates/             Dashboard HTML
static/                CSS and browser-side table search/filtering
sample_data/           Safe fictional CSV exports
tests/                 Automated reconciliation checks
```
