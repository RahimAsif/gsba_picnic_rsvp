import os
import json
import sqlite3
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RENDER_DISK_DIR = "/var/data"


def resolve_db_path():
    candidates = []

    env_path = os.getenv("SQLITE_DB_PATH")
    if env_path:
        candidates.append(env_path)

    candidates.extend([
        os.path.join(RENDER_DISK_DIR, "rsvp.db"),
        os.path.join(BASE_DIR, "rsvp.db"),
        "/tmp/rsvp.db",
    ])

    for path in candidates:
        try:
            directory = os.path.dirname(path) or "."
            os.makedirs(directory, exist_ok=True)
            with open(path, "a", encoding="utf-8"):
                pass
            return path
        except OSError:
            continue

    raise RuntimeError("No writable path available for SQLite database")


DB_PATH = resolve_db_path()
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

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


def is_admin_authorized():
    token = request.headers.get("X-Admin-Token", "")
    return bool(ADMIN_TOKEN) and token == ADMIN_TOKEN


# ---------------------------------------------------------------------------
# REST API
# ---------------------------------------------------------------------------

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "db_path": DB_PATH,
        "db_exists": os.path.exists(DB_PATH),
        "admin_token_configured": bool(ADMIN_TOKEN),
    })


@app.route("/api/admin/db-download", methods=["GET"])
def download_db():
    if not is_admin_authorized():
        return jsonify({"error": "Unauthorized"}), 401

    if not os.path.exists(DB_PATH):
        return jsonify({"error": "Database file not found"}), 404

    return send_file(
        DB_PATH,
        as_attachment=True,
        download_name="rsvp.db",
        mimetype="application/x-sqlite3",
    )


@app.route("/api/admin/reset", methods=["POST"])
def reset_db_data():
    if not is_admin_authorized():
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    if data.get("confirm") != "RESET":
        return jsonify({"error": "Confirmation required. Send {\"confirm\": \"RESET\"}."}), 400

    with get_db() as conn:
        conn.execute("DELETE FROM rsvps")
        conn.execute("DELETE FROM sqlite_sequence WHERE name = 'rsvps'")
        conn.commit()
        summary = get_summary(conn)

    return jsonify({"message": "RSVP data reset successfully", "summary": summary})

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

init_db()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
