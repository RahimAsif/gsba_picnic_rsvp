import os
import json
import re
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
ALLOWED_FOOD_CHOICES = {"Chicken", "Goat", "Veg/Non-Meat"}
ALLOWED_CHILD_FOOD_CHOICES = {"Chicken", "Goat", "Veg/Non-Meat", "Pizza And Nuggets"}
FOOD_NORMALIZATION = {
    "chicken": "Chicken",
    "goat": "Goat",
    "vegetable": "Veg/Non-Meat",
    "veg/non-meat": "Veg/Non-Meat",
    "veg / non-meat": "Veg/Non-Meat",
    "pizza and nuggets": "Pizza And Nuggets",
}
EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

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
                child_food_preferences TEXT NOT NULL DEFAULT '[]',
                adult_food_preferences TEXT NOT NULL DEFAULT '[]',
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        existing_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(rsvps)").fetchall()
        }
        if "adult_food_preferences" not in existing_columns:
            conn.execute(
                "ALTER TABLE rsvps ADD COLUMN adult_food_preferences TEXT NOT NULL DEFAULT '[]'"
            )
        if "child_food_preferences" not in existing_columns:
            conn.execute(
                "ALTER TABLE rsvps ADD COLUMN child_food_preferences TEXT NOT NULL DEFAULT '[]'"
            )

        conn.commit()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def row_to_dict(row):
    d = dict(row)
    d["child_ages"] = json.loads(d["child_ages"])
    d["child_food_preferences"] = json.loads(d.get("child_food_preferences", "[]"))
    d["adult_food_preferences"] = json.loads(d.get("adult_food_preferences", "[]"))
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
    child_food_preferences = data.get("child_food_preferences", [])
    adult_food_preferences = data.get("adult_food_preferences", [])

    # Validation
    if not name or not email:
        return jsonify({"error": "Name and email are required."}), 400
    if not EMAIL_REGEX.match(email):
        return jsonify({"error": "Email is not in the correct format."}), 400
    if not isinstance(adults, int) or adults < 1:
        return jsonify({"error": "At least 1 adult is required."}), 400
    if adults > 10:
        return jsonify({"error": "You may RSVP up to 10 adults maximum."}), 400
    if not isinstance(children, int) or children < 0:
        return jsonify({"error": "Children must be 0 or more."}), 400
    if not isinstance(child_ages, list):
        return jsonify({"error": "Child ages must be a list."}), 400
    if len(child_ages) != children:
        return jsonify({"error": "Provide one age for each child."}), 400
    for age in child_ages:
        if not isinstance(age, int) or age < 0 or age > 19:
            return jsonify({"error": "Child ages must be between 0 and 19."}), 400

    if not isinstance(child_food_preferences, list):
        return jsonify({"error": "Child food preferences must be a list."}), 400

    normalized_child_food_preferences = []
    for choice in child_food_preferences:
        if not isinstance(choice, str):
            return jsonify({"error": "Invalid child food preference value."}), 400
        normalized_choice = FOOD_NORMALIZATION.get(choice.strip().lower(), choice.strip().title())
        if normalized_choice not in ALLOWED_CHILD_FOOD_CHOICES:
            return jsonify({"error": "Child food preference must be Chicken, Goat, Veg/Non-Meat, or Pizza and Nuggets."}), 400
        normalized_child_food_preferences.append(normalized_choice)

    if len(normalized_child_food_preferences) != children:
        return jsonify({"error": "Provide one food preference for each child."}), 400

    if not isinstance(adult_food_preferences, list):
        return jsonify({"error": "Adult food preferences must be a list."}), 400

    normalized_food_preferences = []
    for choice in adult_food_preferences:
        if not isinstance(choice, str):
            return jsonify({"error": "Invalid food preference value."}), 400
        normalized_choice = FOOD_NORMALIZATION.get(choice.strip().lower(), choice.strip().title())
        if normalized_choice not in ALLOWED_FOOD_CHOICES:
            return jsonify({"error": "Food preference must be Chicken, Goat, or Veg/Non-Meat."}), 400
        normalized_food_preferences.append(normalized_choice)

    if len(normalized_food_preferences) != adults:
        return jsonify({"error": "Provide one food preference for each adult."}), 400

    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM rsvps WHERE email = ?", (email,)
        ).fetchone()

        conn.execute(
            "INSERT INTO rsvps (name, email, adults, children, child_ages, child_food_preferences, adult_food_preferences) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(email) DO UPDATE SET "
            "name = excluded.name, "
            "adults = excluded.adults, "
            "children = excluded.children, "
            "child_ages = excluded.child_ages, "
            "child_food_preferences = excluded.child_food_preferences, "
            "adult_food_preferences = excluded.adult_food_preferences, "
            "created_at = CURRENT_TIMESTAMP",
            (
                name,
                email,
                adults,
                children,
                json.dumps(child_ages),
                json.dumps(normalized_child_food_preferences),
                json.dumps(normalized_food_preferences),
            ),
        )
        conn.commit()

        rsvp_row = conn.execute(
            "SELECT * FROM rsvps WHERE email = ?", (email,)
        ).fetchone()
        summary = get_summary(conn)

    return jsonify({
        "rsvp": row_to_dict(rsvp_row),
        "summary": summary,
        "updated": bool(existing),
    }), 200 if existing else 201


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

init_db()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
