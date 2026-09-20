"""SQLite persistence layer for PayFlow backend data."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def connect(path: str | Path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    try:
        yield db
        db.commit()
    finally:
        db.close()


def init_db(path: str | Path) -> None:
    with connect(path) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS reconciliations (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            merchant_count INTEGER NOT NULL, provider_count INTEGER NOT NULL,
            matched_count INTEGER NOT NULL, issue_count INTEGER NOT NULL,
            merchant_total REAL NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS reconciliation_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, reconciliation_id INTEGER NOT NULL,
            transaction_id TEXT NOT NULL, merchant_amount TEXT, provider_amount TEXT,
            currency TEXT NOT NULL, date TEXT NOT NULL, status TEXT NOT NULL, note TEXT NOT NULL,
            FOREIGN KEY (reconciliation_id) REFERENCES reconciliations(id)
        );
        """)


def create_user(path: str | Path, username: str, email: str, password_hash: str) -> int:
    with connect(path) as db:
        return db.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)", (username, email, password_hash)).lastrowid


def get_user(path: str | Path, username: str):
    with connect(path) as db:
        return db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def save_report(path: str | Path, user_id: int, result: dict) -> int:
    summary = result["summary"]
    with connect(path) as db:
        report_id = db.execute("""
            INSERT INTO reconciliations (user_id, merchant_count, provider_count, matched_count, issue_count, merchant_total)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, summary["merchant_count"], summary["provider_count"], summary["matched"], summary["issues"], summary["merchant_total"])).lastrowid
        db.executemany("""
            INSERT INTO reconciliation_transactions (reconciliation_id, transaction_id, merchant_amount, provider_amount, currency, date, status, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [(report_id, row["transaction_id"], row["merchant_amount"], row["provider_amount"], row["currency"], row["date"], row["status"], row["note"])
              for row in result["transactions"]])
        return report_id


def reports_for_user(path: str | Path, user_id: int):
    with connect(path) as db:
        return db.execute("SELECT * FROM reconciliations WHERE user_id = ? ORDER BY id DESC LIMIT 10", (user_id,)).fetchall()


def report_for_user(path: str | Path, report_id: int, user_id: int):
    with connect(path) as db:
        report = db.execute("SELECT * FROM reconciliations WHERE id = ? AND user_id = ?", (report_id, user_id)).fetchone()
        rows = db.execute("""
            SELECT transaction_id, merchant_amount, provider_amount, currency, date, status, note
            FROM reconciliation_transactions WHERE reconciliation_id = ? ORDER BY transaction_id
        """, (report_id,)).fetchall()
    return report, rows
