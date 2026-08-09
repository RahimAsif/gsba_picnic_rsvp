import os
import json
import sqlite3
from flask import Flask, request, jsonify
from flask_cors import CORS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "rsvp.db")

app = Flask(__name__)
CORS(app)


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rsvps (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                email       TEXT    NOT NULL UNIQUE,
                adults      INTEGER NOT NULL,
                children    INTEGER NOT NULL DEFAULT 0,
                child_ages  TEXT    NOT NULL DEFAULT '[]',
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def row_to_dict(row):
    d = dict(row)
    d["child_ages"] = json.loads(d["child_ages"])
    return d


def get_summary(conn):
    row = conn.execute(
        "SELECT COALESCE(SUM(adults), 0) AS total_adults, "
        "COALESCE(SUM(children), 0) AS total_children FROM rsvps"
    ).fetchone()
    return {"total_adults": row["total_adults"], "total_children": row["total_children"]}


# ---------------------------------------------------------------------------
# REST API
# ---------------------------------------------------------------------------

@app.route("/api/rsvps", methods=["GET"])
def get_rsvps():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM rsvps ORDER BY created_at ASC"
        ).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.route("/api/summary", methods=["GET"])
def get_summary_route():
    with get_db() as conn:
        return jsonify(get_summary(conn))


@app.route("/api/rsvp", methods=["POST"])
def post_rsvp():
    data = request.get_json(force=True)

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    adults = data.get("adults")
    children = data.get("children", 0)
    child_ages = data.get("child_ages", [])

    # Validation
    if not name or not email:
        return jsonify({"error": "Name and email are required."}), 400
    if not isinstance(adults, int) or adults < 1:
        return jsonify({"error": "At least 1 adult is required."}), 400
    if adults > 10:
        return jsonify({"error": "You may RSVP up to 10 adults maximum."}), 400

    with get_db() as conn:
        # Check for duplicate email
        existing = conn.execute(
            "SELECT id FROM rsvps WHERE email = ?", (email,)
        ).fetchone()
        if existing:
            return jsonify({"error": "This email has already been used for an RSVP."}), 409

        conn.execute(
            "INSERT INTO rsvps (name, email, adults, children, child_ages) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, email, adults, children, json.dumps(child_ages)),
        )
        conn.commit()

        rsvp_row = conn.execute(
            "SELECT * FROM rsvps WHERE email = ?", (email,)
        ).fetchone()
        summary = get_summary(conn)

    return jsonify({"rsvp": row_to_dict(rsvp_row), "summary": summary}), 201


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
