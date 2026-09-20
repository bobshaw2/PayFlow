from __future__ import annotations

import csv
import io
import os
import re
from pathlib import Path

from flask import Flask, Response, abort, flash, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from database import create_user, get_user, init_db, report_for_user, reports_for_user, save_report
from reconciliation import REQUIRED_COLUMNS, ReconciliationError, reconcile

BASE_DIR = Path(__file__).resolve().parent
ALLOWED_EXTENSIONS = {"csv"}


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    data_dir = Path(os.environ.get("PAYFLOW_DATA_DIR", BASE_DIR))
    data_dir.mkdir(parents=True, exist_ok=True)
    app.config.from_mapping(SECRET_KEY=os.environ.get("SECRET_KEY", "payflow-development-key"), DATABASE=str(data_dir / "payflow.db"))
    if test_config:
        app.config.update(test_config)
    init_db(app.config["DATABASE"])

    def login_required():
        if "user_id" not in session:
            flash("Please log in to access your dashboard.", "error")
            return redirect(url_for("login"))
        return None

    def read_upload(field_name: str) -> list[dict[str, str]]:
        upload = request.files.get(field_name)
        label = "Merchant" if field_name == "merchant_file" else "Payment-provider"
        if not upload or not upload.filename:
            raise ReconciliationError(f"Please select a {label.lower()} CSV file.")
        if "." not in upload.filename or upload.filename.rsplit(".", 1)[1].lower() not in ALLOWED_EXTENSIONS:
            raise ReconciliationError(f"{label} file must be a .csv file.")
        try:
            rows = list(csv.DictReader(io.StringIO(upload.stream.read().decode("utf-8-sig"))))
        except UnicodeDecodeError as exc:
            raise ReconciliationError(f"{label} CSV must use UTF-8 text encoding.") from exc
        if not rows:
            raise ReconciliationError(f"{label} CSV has no transaction rows.")
        if not rows[0] or not set(REQUIRED_COLUMNS).issubset(rows[0]):
            raise ReconciliationError(f"{label} CSV needs these columns: {', '.join(REQUIRED_COLUMNS)}.")
        return rows

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if "user_id" in session:
            return redirect(url_for("index"))
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            if not re.fullmatch(r"[A-Za-z0-9_]{3,30}", username):
                flash("Username must be 3–30 letters, numbers, or underscores.", "error")
            elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                flash("Enter a valid email address.", "error")
            elif len(password) < 8:
                flash("Password must be at least 8 characters.", "error")
            elif get_user(app.config["DATABASE"], username):
                flash("That username is already in use.", "error")
            else:
                try:
                    user_id = create_user(app.config["DATABASE"], username, email, generate_password_hash(password))
                except Exception:
                    flash("That email address is already registered.", "error")
                else:
                    session["user_id"], session["username"] = user_id, username
                    flash("Account created. Welcome to PayFlow!", "success")
                    return redirect(url_for("index"))
        return render_template("auth.html", mode="signup")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if "user_id" in session:
            return redirect(url_for("index"))
        if request.method == "POST":
            user = get_user(app.config["DATABASE"], request.form.get("username", "").strip())
            if not user or not check_password_hash(user["password_hash"], request.form.get("password", "")):
                flash("Incorrect username or password.", "error")
            else:
                session["user_id"], session["username"] = user["id"], user["username"]
                return redirect(url_for("index"))
        return render_template("auth.html", mode="login")

    @app.post("/logout")
    def logout():
        session.clear()
        flash("You have been logged out.", "success")
        return redirect(url_for("login"))

    @app.get("/")
    def index():
        redirect_response = login_required()
        if redirect_response:
            return redirect_response
        with (BASE_DIR / "sample_data" / "merchant_transactions.csv").open(encoding="utf-8") as merchant_file, (BASE_DIR / "sample_data" / "provider_transactions.csv").open(encoding="utf-8") as provider_file:
            result = reconcile(list(csv.DictReader(merchant_file)), list(csv.DictReader(provider_file)))
        return render_template("index.html", result=result, showing_sample=True, report_id=None, history=reports_for_user(app.config["DATABASE"], session["user_id"]))

    @app.get("/sample-data/<path:filename>")
    def sample_data(filename: str):
        return send_from_directory(BASE_DIR / "sample_data", filename, as_attachment=True)

    @app.post("/reconcile")
    def reconcile_uploads():
        redirect_response = login_required()
        if redirect_response:
            return redirect_response
        try:
            result = reconcile(read_upload("merchant_file"), read_upload("provider_file"))
        except ReconciliationError as exc:
            flash(str(exc), "error")
            return redirect(url_for("index"))
        report_id = save_report(app.config["DATABASE"], session["user_id"], result)
        flash("Reconciliation saved to your backend history.", "success")
        return render_template("index.html", result=result, showing_sample=False, report_id=report_id, history=reports_for_user(app.config["DATABASE"], session["user_id"]))

    @app.get("/export/<int:report_id>")
    def export_report(report_id: int):
        redirect_response = login_required()
        if redirect_response:
            return redirect_response
        report, rows = report_for_user(app.config["DATABASE"], report_id, session["user_id"])
        if not report:
            abort(404)
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["transaction_id", "merchant_amount", "provider_amount", "currency", "date", "status", "note"])
        writer.writeheader()
        writer.writerows(dict(row) for row in rows)
        return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f"attachment; filename={secure_filename('payflow-reconciliation-report.csv')}"})

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
