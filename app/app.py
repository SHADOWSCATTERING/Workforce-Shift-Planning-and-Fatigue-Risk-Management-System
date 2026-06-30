"""
app.py
-------
Flask REST API for the Workforce Shift Planning and Fatigue Risk
Management System.

Run with:
    python app/app.py
Then visit:
    http://localhost:5000/api/health

See README.md for the full endpoint list and example requests.
"""
import os
import sys
from datetime import datetime, timezone

# Allow running this file directly (python app/app.py) by adding the
# project root to sys.path so `import src...` works either way.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()  # must happen BEFORE importing src.ai_service, which reads ANTHROPIC_API_KEY at import time

from flask import Flask, request, jsonify

from src.database import get_connection, init_db, seed_from_csv, DB_PATH
from src.fatigue_engine import FatigueEngine
from src.ai_service import explain_fatigue_risk, explain_conflict, is_ai_configured

app = Flask(__name__)

# Initialize database on startup if running on Vercel
if "VERCEL" in os.environ:
    if not os.path.exists(DB_PATH):
        print("Vercel environment detected. Initializing database in /tmp...")
        init_db(reset=True)
        seed_from_csv()

# Enable simple CORS globally for local front-end testing
@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        res = Flask.make_response(app, "")
        res.headers["Access-Control-Allow-Origin"] = "*"
        res.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        res.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return res

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def error_response(message: str, status: int = 400):
    return jsonify({"error": message}), status


def require_fields(payload: dict, fields: list):
    missing = [f for f in fields if not payload.get(f)]
    if missing:
        return f"Missing required field(s): {', '.join(missing)}"
    return None


# ---------------------------------------------------------------------
# Health / meta
# ---------------------------------------------------------------------
@app.route("/api/health", methods=["GET"])
def health():
    db_exists = os.path.exists(DB_PATH)
    return jsonify({
        "status": "ok",
        "database_initialized": db_exists,
        "ai_configured": is_ai_configured(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ---------------------------------------------------------------------
# Employees
# ---------------------------------------------------------------------
@app.route("/api/employees", methods=["GET"])
def list_employees():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM employees ORDER BY employee_id").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/employees/<employee_id>", methods=["GET"])
def get_employee(employee_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM employees WHERE employee_id = ?", (employee_id,)).fetchone()
    conn.close()
    if not row:
        return error_response(f"Employee {employee_id} not found", 404)
    return jsonify(dict(row))


@app.route("/api/employees", methods=["POST"])
def create_employee():
    payload = request.get_json(force=True, silent=True) or {}
    err = require_fields(payload, ["employee_id", "name"])
    if err:
        return error_response(err)

    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO employees
               (employee_id, name, role, department, employment_type,
                max_weekly_hours, contracted_hours, experience_years, min_rest_hours_required)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload["employee_id"], payload["name"], payload.get("role"),
                payload.get("department"), payload.get("employment_type", "Full-Time"),
                payload.get("max_weekly_hours", 48), payload.get("contracted_hours", 40),
                payload.get("experience_years"), payload.get("min_rest_hours_required", 11),
            ),
        )
        conn.commit()
    except Exception as exc:
        conn.close()
        return error_response(f"Could not create employee: {exc}")
    conn.close()
    return jsonify({"message": "Employee created", "employee_id": payload["employee_id"]}), 201


# ---------------------------------------------------------------------
# Shifts
# ---------------------------------------------------------------------
@app.route("/api/shifts", methods=["GET"])
def list_shifts():
    employee_id = request.args.get("employee_id")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    query = "SELECT * FROM shifts WHERE 1=1"
    params = []
    if employee_id:
        query += " AND employee_id = ?"
        params.append(employee_id)
    if start_date:
        query += " AND shift_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND shift_date <= ?"
        params.append(end_date)
    query += " ORDER BY shift_date, start_time"

    conn = get_connection()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/shifts/<shift_id>", methods=["GET"])
def get_shift(shift_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM shifts WHERE shift_id = ?", (shift_id,)).fetchone()
    conn.close()
    if not row:
        return error_response(f"Shift {shift_id} not found", 404)
    return jsonify(dict(row))


@app.route("/api/shifts/validate", methods=["POST"])
def validate_shift():
    """Dry-run check BEFORE committing a shift assignment. Returns the
    projected fatigue impact, any new violations, an AI explanation, and
    rule-based safer alternatives. Does not write to the database."""
    payload = request.get_json(force=True, silent=True) or {}
    err = require_fields(payload, ["employee_id", "shift_date", "start_time", "end_time"])
    if err:
        return error_response(err)

    eng = FatigueEngine()
    try:
        check = eng.validate_new_shift(
            payload["employee_id"], payload["shift_date"],
            payload["start_time"], payload["end_time"], payload.get("shift_type"),
        )
        if "error" in check:
            return error_response(check["error"], 404)

        alternatives = []
        if not check["safe_to_assign"]:
            alternatives = eng.suggest_safer_alternatives(
                payload["employee_id"], payload["shift_date"],
                payload["start_time"], payload["end_time"], payload.get("shift_type"),
            )

        explanation_input = {
            "employee_name": check["employee_name"],
            "risk_level": check["projected_risk_level"],
            "violations": check["would_introduce_violations"],
        }
        ai_explanation = explain_fatigue_risk(explanation_input, alternatives)
    finally:
        eng.close()

    return jsonify({**check, "safer_alternatives": alternatives, "ai_explanation": ai_explanation})


@app.route("/api/shifts", methods=["POST"])
def create_shift():
    """Create a shift. By default this BLOCKS hard conflicts (overlaps)
    unless force=true is passed; soft fatigue risk is allowed through but
    flagged in the response so a manager can make an informed call."""
    payload = request.get_json(force=True, silent=True) or {}
    err = require_fields(payload, ["shift_id", "employee_id", "shift_date", "start_time", "end_time"])
    if err:
        return error_response(err)

    force = bool(payload.get("force", False))

    eng = FatigueEngine()
    try:
        check = eng.validate_new_shift(
            payload["employee_id"], payload["shift_date"],
            payload["start_time"], payload["end_time"], payload.get("shift_type"),
        )
        if "error" in check:
            return error_response(check["error"], 404)

        has_overlap = any(v["rule_id"] == "R006" for v in check["would_introduce_violations"])
        if has_overlap and not force:
            ai_explanation = explain_conflict({
                "rule_id": "R006", "rule_name": "Shift Overlap / Double-Booking",
                "severity": "Critical",
                "detail": "The new shift overlaps with an existing shift for this employee.",
                "employee_name": check["employee_name"],
            })
            return jsonify({
                "error": "This shift conflicts with an existing shift for this employee.",
                "blocked": True,
                "validation": check,
                "ai_explanation": ai_explanation,
                "hint": "Resend with \"force\": true to assign anyway (not recommended).",
            }), 409
    finally:
        eng.close()

    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO shifts (shift_id, employee_id, shift_date, shift_type,
               start_time, end_time, location, department)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload["shift_id"], payload["employee_id"], payload["shift_date"],
                payload.get("shift_type", "Day"), payload["start_time"], payload["end_time"],
                payload.get("location"), payload.get("department"),
            ),
        )
        conn.commit()
    except Exception as exc:
        conn.close()
        return error_response(f"Could not create shift: {exc}")
    conn.close()

    return jsonify({
        "message": "Shift created",
        "shift_id": payload["shift_id"],
        "fatigue_warnings": check["would_introduce_violations"],
        "projected_risk_level": check["projected_risk_level"],
    }), 201


@app.route("/api/shifts/<shift_id>", methods=["DELETE"])
def delete_shift(shift_id):
    conn = get_connection()
    cur = conn.execute("DELETE FROM shifts WHERE shift_id = ?", (shift_id,))
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    if not deleted:
        return error_response(f"Shift {shift_id} not found", 404)
    return jsonify({"message": f"Shift {shift_id} deleted"})


# ---------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------
@app.route("/api/availability/<employee_id>", methods=["GET"])
def get_availability(employee_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM availability WHERE employee_id = ? ORDER BY date", (employee_id,)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ---------------------------------------------------------------------
# Fatigue rules (reference data)
# ---------------------------------------------------------------------
@app.route("/api/fatigue-rules", methods=["GET"])
def list_fatigue_rules():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM fatigue_rules").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ---------------------------------------------------------------------
# Fatigue risk analysis (the core AI + business logic feature)
# ---------------------------------------------------------------------
@app.route("/api/employees/<employee_id>/fatigue-risk", methods=["GET"])
def employee_fatigue_risk(employee_id):
    """Full fatigue-risk analysis for one employee, with an AI-generated
    plain-English explanation and (if risky) rule-based safer-alternative
    suggestions for their most recent flagged shift."""
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    eng = FatigueEngine()
    try:
        analysis = eng.analyze_employee(employee_id, start_date, end_date)
        if "error" in analysis:
            return error_response(analysis["error"], 404)

        alternatives = []
        if analysis["violations"]:
            shifts = eng.get_shifts_for_employee(employee_id, start_date, end_date)
            if shifts:
                last_shift = shifts[-1]
                alternatives = eng.suggest_safer_alternatives(
                    employee_id, last_shift["shift_date"],
                    last_shift["start_time"], last_shift["end_time"], last_shift.get("shift_type"),
                )
        ai_explanation = explain_fatigue_risk(analysis, alternatives)
    finally:
        eng.close()

    return jsonify({**analysis, "safer_alternatives": alternatives, "ai_explanation": ai_explanation})


@app.route("/api/employees/<employee_id>/schedule", methods=["GET"])
def employee_schedule(employee_id):
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    eng = FatigueEngine()
    try:
        employee = eng.get_employee(employee_id)
        if not employee:
            return error_response(f"Employee {employee_id} not found", 404)
        shifts = eng.get_shifts_for_employee(employee_id, start_date, end_date)
    finally:
        eng.close()
    return jsonify({"employee": employee, "shifts": shifts})


@app.route("/api/dashboard/risk-summary", methods=["GET"])
def dashboard_risk_summary():
    """Workforce-wide fatigue risk dashboard: counts by risk level and the
    top at-risk employees. Powers the manager-facing dashboard view."""
    eng = FatigueEngine()
    try:
        summary = eng.workforce_risk_summary()
    finally:
        eng.close()
    return jsonify(summary)


# ---------------------------------------------------------------------
# Admin / setup
# ---------------------------------------------------------------------
@app.route("/api/admin/seed", methods=["POST"])
def admin_seed():
    """Convenience endpoint to (re)initialize and seed the database from
    the starter CSVs in data/. Intended for local dev/demo use only."""
    reset = bool((request.get_json(silent=True) or {}).get("reset", True))
    init_db(reset=reset)
    seed_from_csv()
    return jsonify({"message": "Database initialized and seeded."})


@app.errorhandler(404)
def not_found(e):
    return error_response("Endpoint not found", 404)


@app.errorhandler(500)
def server_error(e):
    return error_response("Internal server error", 500)


if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print("No database found - initializing and seeding from starter CSVs...")
        init_db(reset=True)
        seed_from_csv()
    app.run(debug=True, host="0.0.0.0", port=5000)
