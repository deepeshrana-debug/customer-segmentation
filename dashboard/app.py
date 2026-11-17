"""
Customer Segmentation Dashboard
===============================

A small local Flask app that visualises the results produced by ``src/main.py``.

What it does
------------
* Reads ``segment_profile.csv`` and ``segments.csv`` from two result folders:
    output/      -> the automatic k (currently k = 2)
    output_k4/   -> the forced k = 4 result set
* Serves a single page (templates/index.html) with pie charts, bar charts and a
  formatted segment table.
* Exposes a tiny JSON API (``/api/data``) so the browser can switch between the
  two result sets without a page reload.

The CSVs are re-read on *every* request instead of once at startup. That costs a
few milliseconds on a dataset this size and means the dashboard always reflects
the latest ``main.py`` run -- just refresh the browser.

Run
---
    pip install flask pandas
    python dashboard/app.py
    # open http://localhost:8000
"""

from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, redirect, render_template, request, url_for

# The number maths and the plain-English sentences live in src/summary.py so
# they can be tested without starting the web server.
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from summary import (  # noqa: E402
    FIELDS,
    check_numbers,
    file_numbers,
    file_sentences,
    parse_list,
    percentages,
    read_document,
    read_upload,
    run_segmentation,
    sentences,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# BASE_DIR is the project root (the folder that contains src/, output/ ...).
# app.py lives in dashboard/, so we go one level up from its own folder.
BASE_DIR = Path(__file__).resolve().parent.parent

# One entry per result set shown by the toggle at the top of the page.
# The order here is the order the toggle buttons appear in.
RESULT_SETS = [
    {"id": "k2", "folder": "output", "label": "k = 2", "note": "Chosen automatically (best silhouette)"},
    {"id": "k4", "folder": "output_k4", "label": "k = 4", "note": "Forced with --k 4"},
]

app = Flask(__name__)

# The owner's typed numbers are saved in a small SQLite file kept next to
# this script. SQLite ships with Python, so there is nothing extra to install.
DB_PATH = Path(__file__).resolve().parent / "entries.db"


def get_db() -> sqlite3.Connection:
    """Open the SQLite file, creating the table the first time we run."""
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS entries (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            saved_at  TEXT    NOT NULL,
            total     INTEGER NOT NULL,
            most      INTEGER NOT NULL DEFAULT 0,
            regular   INTEGER NOT NULL DEFAULT 0,
            least     INTEGER NOT NULL DEFAULT 0,
            frequent  INTEGER NOT NULL DEFAULT 0,
            last_month INTEGER NOT NULL DEFAULT 0,
            big_spenders INTEGER NOT NULL DEFAULT 0
        )
        """
    )

    # Every "Add your data" run is kept here as one row of JSON. Storing the
    # whole result (numbers, percentages, sentences, report, segments) means
    # an old entry can be opened again exactly as it was.
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            saved_at  TEXT    NOT NULL,
            source    TEXT    NOT NULL,      -- 'CSV' or 'Typed'
            title     TEXT    NOT NULL,      -- the file name, or a short note
            payload   TEXT    NOT NULL       -- the result as JSON
        )
        """
    )
    return connection


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------
def _read_csv(path: Path) -> pd.DataFrame | None:
    """Return the CSV at *path* as a DataFrame, or None if it is missing.

    Returning None (instead of raising) lets the page render a friendly
    "folder not found" message rather than a 500 error -- useful when the user
    has not yet run ``main.py --k 4 --out output_k4``.
    """
    if not path.exists():
        return None
    return pd.read_csv(path)


def _clean_number(value, default=0.0) -> float:
    """Convert a pandas/numpy value into a plain float safe for JSON.

    NaN and infinity are not valid JSON, so they are folded into *default*.
    This guards against an empty CSV leaving blanks in the summary cards.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(number) or math.isinf(number):
        return default
    return number


def load_result_set(folder: str) -> dict:
    """Build the dict the front-end needs for one result folder.

    Reads ``segment_profile.csv`` (one row per segment) and, if present,
    ``segments.csv`` (one row per customer, used for the totals).
    """
    directory = BASE_DIR / folder
    profile_df = _read_csv(directory / "segment_profile.csv")
    segments_df = _read_csv(directory / "segments.csv")

    # --- The folder has not been generated yet -----------------------------
    if profile_df is None:
        return {
            "available": False,
            "folder": folder,
            "message": (
                f"No results found in '{folder}/'. "
                f"Run: python src/main.py --out {folder}"
            ),
        }

    # --- Per-segment rows --------------------------------------------------
    segments = []
    for row in profile_df.to_dict(orient="records"):
        segments.append(
            {
                "cluster": int(row.get("cluster", 0)),
                "segment": str(row.get("segment", "Unnamed")),
                "customers": int(_clean_number(row.get("customers"))),
                "recency": _clean_number(row.get("recency")),
                "frequency": _clean_number(row.get("frequency")),
                "monetary": _clean_number(row.get("monetary")),
                # The column header in the CSV is literally 'revenue_share_%'
                "revenue_share": _clean_number(row.get("revenue_share_%")),
            }
        )

    # Largest segment first: the table and the charts read more naturally when
    # the biggest group leads.
    segments.sort(key=lambda item: item["customers"], reverse=True)

    # --- Totals for the summary cards --------------------------------------
    total_customers = sum(item["customers"] for item in segments)

    # Total revenue: prefer the customer-level file because it holds the real
    # money figure. Fall back to customers x average spend when the customer
    # file is missing (which still gives the identical total for k-means,
    # since every customer appears in exactly one segment).
    if segments_df is not None and "monetary" in segments_df.columns:
        total_revenue = _clean_number(pd.to_numeric(segments_df["monetary"], errors="coerce").sum())
    else:
        total_revenue = sum(item["customers"] * item["monetary"] for item in segments)

    # The segment holding the largest share of revenue drives one summary card
    # and the "biggest earner" callout in the pie chart note.
    top_segment = max(segments, key=lambda item: item["revenue_share"])

    return {
        "available": True,
        "folder": folder,
        "segments": segments,
        "summary": {
            "total_customers": total_customers,
            "total_revenue": round(total_revenue, 2),
            "segment_count": len(segments),
            "top_segment": top_segment["segment"],
            "top_segment_share": top_segment["revenue_share"],
        },
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    """Render the dashboard shell. Data is fetched from /api/data by the page."""
    return render_template("index.html", result_sets=RESULT_SETS)


@app.route("/api/data")
def api_data():
    """Return every result set as JSON: { 'k2': {...}, 'k4': {...} }."""
    payload = {item["id"]: load_result_set(item["folder"]) for item in RESULT_SETS}
    response = jsonify(payload)
    # Tell the browser not to cache, so a fresh `main.py` run shows up on reload.
    response.headers["Cache-Control"] = "no-store"
    return response


# ---------------------------------------------------------------------------
# "Enter your numbers" page
# ---------------------------------------------------------------------------
# The owner types seven numbers. We show them back as cards, a pie chart and
# a bar chart, then save them to SQLite so they are kept for next time.

def _blank_values() -> dict:
    """Every box, empty. Used the first time the page opens."""
    return {key: "" for key, _label, _hint in FIELDS}


def _read_form(form) -> tuple[dict, dict]:
    """Read the seven boxes and return (values, errors).

    values holds the raw text the owner typed, so the boxes can be shown again
    with what they typed still in them. errors maps a box key to a short
    message in plain words.
    """
    values, errors = {}, {}

    for key, _label, _hint in FIELDS:
        raw = (form.get(key) or "").strip()
        values[key] = raw

        if raw == "":
            errors[key] = "Please type a number here."
        elif not raw.isdigit():
            errors[key] = "Please type a whole number, like 10. No letters or dots."

    return values, errors


def _as_numbers(values: dict) -> dict:
    """Turn the typed text into real numbers, ignoring boxes that are empty."""
    numbers = {}
    for key, raw in values.items():
        if str(raw).strip().isdigit():
            numbers[key] = int(str(raw).strip())
    return numbers


def _build_results(numbers: dict) -> dict:
    """Make the cards, the percentages and the sentences for the page."""
    shares = percentages(numbers)
    return {
        "numbers": numbers,
        "percentages": shares,
        "sentences": sentences(numbers),
        "cards": [
            {
                "key": key,
                "label": label,
                "number": numbers.get(key, 0),
                "percent": shares.get(key),
            }
            for key, label, _hint in FIELDS
        ],
        "total": numbers.get("total", 0),
    }


@app.route("/enter", methods=["GET", "POST"])
def enter_numbers():
    """Show the form (GET), or check the numbers and save them (POST)."""
    values = _blank_values()
    errors: dict = {}
    warnings: list = []
    results = None          # filled in once we have numbers to show
    typed_lines = ""        # the big text box on the "Type a list" tab
    unknown_lines: list = []
    active_tab = "form"

    if request.method == "POST":
        active_tab = request.form.get("tab", "form")
        typed_lines = request.form.get("typed_list", "")
        values, errors = _read_form(request.form)

        # --- The "Type a list" tab ----------------------------------------
        # Read the lines and put what we understood into the form boxes, so
        # the owner can check them before saving.
        if active_tab == "list" and typed_lines.strip():
            found, unknown_lines = parse_list(typed_lines)
            for key, number in found.items():
                values[key] = str(number)
                errors.pop(key, None)   # a line we read fills its box

        numbers = _as_numbers(values)
        warnings = check_numbers(numbers)

        # Warnings never block the save: they ask the owner to double-check.
        # Errors (empty boxes, letters) do block it.
        if not errors:
            connection = get_db()
            saved_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            connection.execute(
                """INSERT INTO entries
                   (saved_at, total, most, regular, least, frequent,
                    last_month, big_spenders)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    saved_at,
                    numbers.get("total", 0),
                    numbers.get("most", 0),
                    numbers.get("regular", 0),
                    numbers.get("least", 0),
                    numbers.get("frequent", 0),
                    numbers.get("last_month", 0),
                    numbers.get("big_spenders", 0),
                ),
            )
            connection.commit()
            connection.close()

        if numbers:
            results = _build_results(numbers)

    return render_template(
        "enter.html",
        fields=FIELDS,
        values=values,
        errors=errors,
        warnings=warnings,
        results=results,
        typed_lines=typed_lines,
        unknown_lines=unknown_lines,
        active_tab=active_tab,
        saved_at=None,
        entry_id=None,
    )


@app.route("/entries")
def past_entries():
    """Show every saved entry, newest first, with a delete button each."""
    connection = get_db()
    rows = connection.execute("SELECT * FROM entries ORDER BY id DESC").fetchall()
    connection.close()
    return render_template("entries.html", entries=rows, fields=FIELDS)


@app.route("/entries/<int:entry_id>/delete", methods=["POST"])
def delete_entry(entry_id: int):
    """Remove one saved entry, then go back to the list."""
    connection = get_db()
    connection.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
    connection.commit()
    connection.close()
    return redirect(url_for("past_entries"))


@app.route("/entries/<int:entry_id>")
def open_entry(entry_id: int):
    """Open an old entry: show its numbers as cards and charts again."""
    connection = get_db()
    row = connection.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
    connection.close()

    if row is None:
        return redirect(url_for("past_entries"))

    numbers = {key: int(row[key]) for key, _l, _h in FIELDS}

    return render_template(
        "enter.html",
        fields=FIELDS,
        values={k: str(v) for k, v in numbers.items()},
        errors={},
        warnings=[],
        results=_build_results(numbers),
        typed_lines="",
        unknown_lines=[],
        active_tab="form",
        saved_at=row["saved_at"],
        entry_id=entry_id,
    )


# ---------------------------------------------------------------------------
# "Add your data" page
# ---------------------------------------------------------------------------
# Two ways in, one set of results:
#   Option A - upload a CSV file of transactions (POST /upload)
#   Option B - type the seven numbers (POST /typed)
# Both save the finished result to the `runs` table, keyed by an id, so the
# result page can be refreshed or opened later from the history.

MAX_UPLOAD_BYTES = 20 * 1024 * 1024   # 20 MB, as the brief asks

# A tiny example file the owner can download to see the shape we expect.
SAMPLE_CSV_TEXT = """customer_id,invoice_id,invoice_date,quantity,unit_price
10001,INV-001,2024-01-05,2,9.99
10001,INV-002,2024-01-19,1,14.5
10002,INV-003,2024-01-07,3,4.25
10002,INV-004,2024-02-02,1,4.25
10002,INV-005,2024-02-20,2,4.25
10003,INV-006,2024-01-09,1,25
10004,INV-007,2024-01-12,4,7.5
10004,INV-008,2024-01-26,2,7.5
10004,INV-009,2024-02-11,1,7.5
10005,INV-010,2024-02-15,1,12
"""


def _save_run(source: str, title: str, result: dict) -> int:
    """Store one finished run and return its id."""
    connection = get_db()
    cursor = connection.execute(
        "INSERT INTO runs (saved_at, source, title, payload) VALUES (?, ?, ?, ?)",
        (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            source,
            title,
            json.dumps(result),
        ),
    )
    connection.commit()
    new_id = int(cursor.lastrowid)
    connection.close()
    return new_id


def _load_run(run_id: int) -> dict | None:
    """Read one saved run back, or None if it has been deleted."""
    connection = get_db()
    row = connection.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    connection.close()
    if row is None:
        return None
    return {
        "id": int(row["id"]),
        "saved_at": row["saved_at"],
        "source": row["source"],
        "title": row["title"],
        "result": json.loads(row["payload"]),
    }


def _result_cards(numbers: dict) -> list[dict]:
    """The result cards for either option.

    The typed form has seven boxes; an uploaded file also knows the buyers who
    did not buy last month, and the total revenue. Extra cards only appear
    when the number is there.
    """
    shares = percentages(numbers)
    cards = [
        {
            "key": key,
            "label": label,
            "number": numbers.get(key, 0),
            "percent": shares.get(key),
            "show_customers": False,
        }
        for key, label, _hint in FIELDS
    ]

    if "not_last_month" in numbers:
        cards.append({
            "key": "not_last_month",
            "label": "Did not buy last month",
            "number": numbers["not_last_month"],
            "percent": shares.get("not_last_month"),
            "show_customers": False,
        })

    if "revenue" in numbers:
        cards.append({
            "key": "revenue",
            "label": "Total revenue",
            "number": numbers["revenue"],
            "percent": None,
            "show_customers": False,
        })

    return cards


@app.route("/add-data")
def add_data():
    """Show the page with the two big tabs."""
    return render_template(
        "add_data.html",
        fields=FIELDS,
        values={key: "" for key, _l, _h in FIELDS},
        errors={},
        warnings=[],
        unknown_lines=[],
        message="",
        max_mb=20,
    )


@app.route("/sample.csv")
def sample_csv():
    """Download a small example file, so the owner can see the expected shape."""
    return app.response_class(
        SAMPLE_CSV_TEXT,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=sample-transactions.csv"},
    )


@app.route("/upload", methods=["POST"])
def upload():
    """Option A: clean the uploaded file, count the buyers, save the run."""
    upload_file = request.files.get("csv_file")

    # --- The file itself ------------------------------------------------
    if upload_file is None or upload_file.filename == "":
        return _add_data_error("Please choose a CSV file first.", active_tab="upload")

    if not upload_file.filename.lower().endswith(".csv"):
        return _add_data_error("Please upload a CSV file.", active_tab="upload")

    file_bytes = upload_file.read()
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        return _add_data_error(
            "That file is too big. The largest size is 20 MB.", active_tab="upload"
        )

    # --- Clean it -------------------------------------------------------
    read = read_upload(file_bytes)
    if read["error"]:
        return _add_data_error(
            read["error"], active_tab="upload", report=read.get("report")
        )

    # The uploaded file is only used in memory and never written to disk, so
    # there is nothing to delete afterwards.
    clean = read["clean"]
    numbers = file_numbers(clean)
    segments = run_segmentation(clean)

    result = {
        "source": "CSV",
        "title": upload_file.filename,
        "numbers": numbers,
        "cards": _result_cards(numbers),
        "percentages": percentages(numbers),
        "report": read["report"],
        "summary_line": (
            f"{read['report']['rows_read']:,} rows read. "
            f"{read['report']['rows_used']:,} used. "
            f"{read['report']['rows_removed']:,} removed."
        ),
        "sentences": file_sentences(numbers),
        "segments": segments,
    }
    return redirect(url_for("show_results", run_id=_save_run("CSV", upload_file.filename, result)))


@app.route("/document", methods=["POST"])
def document():
    """Option C: read the numbers out of a document, then show them to check."""
    upload_file = request.files.get("document")

    if upload_file is None or upload_file.filename == "":
        return _add_data_error("Please choose a document first.", active_tab="document")

    file_bytes = upload_file.read()
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        return _add_data_error(
            "That file is too big. The largest size is 20 MB.", active_tab="document"
        )

    read = read_document(upload_file.filename, file_bytes)
    if read["error"]:
        return _add_data_error(read["error"], active_tab="document")

    # Fill the typed boxes so the owner can check every number before saving.
    # The document is used in memory only and never written to disk.
    values = {key: "" for key, _l, _h in FIELDS}
    for key, number in read["values"].items():
        values[key] = str(number)

    return render_template(
        "add_data.html",
        fields=FIELDS,
        values=values,
        errors={},
        warnings=[],
        unknown_lines=read["unknown_lines"],
        missing=[label for key, label, _h in FIELDS if key in read["missing"]],
        from_document=upload_file.filename,
        active_tab="typed",
        message="",
        max_mb=20,
    )


@app.route("/typed", methods=["POST"])
def typed():
    """Option B: check the typed numbers and save the run."""
    values, errors = _read_form(request.form)
    typed_lines = request.form.get("typed_list", "")
    unknown_lines = []
    active_tab = request.form.get("tab", "form")

    # The "Type a list" tab fills the boxes from the text.
    if active_tab == "list" and typed_lines.strip():
        found, unknown_lines = parse_list(typed_lines)
        for key, number in found.items():
            values[key] = str(number)
            errors.pop(key, None)

    numbers = _as_numbers(values)
    warnings = check_numbers(numbers)

    if errors:
        return render_template(
            "add_data.html",
            fields=FIELDS,
            values=values,
            errors=errors,
            warnings=warnings,
            unknown_lines=unknown_lines,
            message="",
            max_mb=20,
        )

    result = {
        "source": "Typed",
        "title": "Numbers you typed",
        "numbers": numbers,
        "cards": _result_cards(numbers),
        "percentages": percentages(numbers),
        "report": None,
        "summary_line": "",
        "sentences": sentences(numbers),
        "segments": {"available": False, "message": "", "segments": []},
        "warnings": warnings,
    }
    return redirect(url_for("show_results", run_id=_save_run("Typed", "Numbers you typed", result)))


def _add_data_error(message: str, active_tab: str = "upload", report: dict | None = None):
    """Show the page again with a plain-English message, never a crash."""
    return render_template(
        "add_data.html",
        fields=FIELDS,
        values={key: "" for key, _l, _h in FIELDS},
        errors={},
        warnings=[],
        unknown_lines=[],
        message=message,
        report=report,
        active_tab=active_tab,
        max_mb=20,
    )


@app.route("/results/<int:run_id>")
def show_results(run_id: int):
    """Show the cards, charts and sentences for one saved run."""
    run = _load_run(run_id)
    if run is None:
        return redirect(url_for("history"))

    return render_template(
        "results.html",
        run=run,
        result=run["result"],
        result_json=json.dumps(run["result"]),
        fields=FIELDS,
    )


@app.route("/history")
def history():
    """Every saved run, newest first, with open and delete buttons."""
    connection = get_db()
    rows = connection.execute(
        "SELECT id, saved_at, source, title FROM runs ORDER BY id DESC"
    ).fetchall()
    connection.close()
    return render_template("history.html", runs=rows)


@app.route("/history/<int:run_id>/delete", methods=["POST"])
def delete_run(run_id: int):
    """Remove one saved run, then go back to the history list."""
    connection = get_db()
    connection.execute("DELETE FROM runs WHERE id = ?", (run_id,))
    connection.commit()
    connection.close()
    return redirect(url_for("history"))


if __name__ == "__main__":
    # Port 8000 as requested (Flask's default is 5000).
    # debug=True gives auto-reload while editing this file.
    app.run(host="127.0.0.1", port=8000, debug=True)
