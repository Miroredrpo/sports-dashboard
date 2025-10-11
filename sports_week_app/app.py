import os
import csv
import io
from functools import wraps
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY")

supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# --- Role Checking Functions ---
def is_admin(user_id):
    try:
        res = supabase.table('admins').select('user_id').eq('user_id', user_id).execute()
        return len(res.data) > 0
    except Exception as e:
        print(e)
        return False

def is_teacher(user_id):
    try:
        res = supabase.table('teachers').select('user_id').eq('user_id', user_id).execute()
        return len(res.data) > 0
    except Exception as e:
        print(e)
        return False

# --- Decorators ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        if not is_admin(session['user']):
            return "<h1>Admin access required</h1>", 403
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---
@app.route("/")
def index():
    return redirect(url_for('login'))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        try:
            # Use the service role key to sign in the user
            user_session = supabase.auth.sign_in_with_password({"email": email, "password": password})
            session['user'] = user_session.user.id
            session['is_admin'] = is_admin(user_session.user.id)
            session['is_teacher'] = is_teacher(user_session.user.id)
            return redirect(url_for('dashboard'))
        except Exception as e:
            return render_template("login.html", error=str(e))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")

@app.route("/admin")
@admin_required
def admin_dashboard():
    return render_template("admin_dashboard.html")

@app.route("/admin/houses")
@admin_required
def manage_houses():
    houses = supabase.table('houses').select('*').execute()
    return render_template("houses.html", houses=houses.data)

@app.route("/admin/houses/add", methods=["POST"])
@admin_required
def add_house():
    try:
        name = request.form.get("name")
        color = request.form.get("color")
        supabase.table('houses').insert({"name": name, "color": color}).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/admin/houses/edit/<int:house_id>", methods=["POST"])
@admin_required
def edit_house(house_id):
    try:
        name = request.form.get("name")
        color = request.form.get("color")
        supabase.table('houses').update({"name": name, "color": color}).eq('id', house_id).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/admin/houses/delete/<int:house_id>")
@admin_required
def delete_house(house_id):
    supabase.table('houses').delete().eq('id', house_id).execute()
    return redirect(url_for('manage_houses'))

# --- Student Import Routes ---
@app.route("/admin/students/import")
@admin_required
def import_students():
    return render_template("import_students.html")

@app.route("/api/admin/import_students_preview", methods=["POST"])
@admin_required
def import_students_preview():
    if 'csv_file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['csv_file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    try:
        # Read file in memory
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_reader = csv.DictReader(stream)

        headers = [h.lower() for h in csv_reader.fieldnames]
        required_headers = ['full_name', 'roll_no', 'house']
        if not all(h in headers for h in required_headers):
            return jsonify({"error": f"Missing required headers. Found: {headers}, Required: {required_headers}"}), 400

        # Fetch existing data for validation
        houses_res = supabase.table('houses').select('id, name').execute()
        house_map = {h['name'].lower(): h['id'] for h in houses_res.data}

        students_res = supabase.table('students').select('roll_no').execute()
        existing_roll_nos = {s['roll_no'] for s in students_res.data if s['roll_no']}

        preview_rows = []
        for row in csv_reader:
            row_data = {k.lower(): v for k, v in row.items()}
            errors = []
            valid = True
            duplicate = False

            if not row_data.get('full_name'):
                errors.append("Missing full_name")
                valid = False

            house_name = row_data.get('house', '').lower()
            if not house_name or house_name not in house_map:
                errors.append(f"Invalid house: {row_data.get('house')}")
                valid = False

            if row_data.get('roll_no') and row_data['roll_no'] in existing_roll_nos:
                duplicate = True # It's a duplicate, but can be updated, so not strictly invalid

            preview_rows.append({
                "data": row_data,
                "valid": valid,
                "errors": errors,
                "duplicate": duplicate
            })

        return jsonify({"headers": headers, "preview_rows": preview_rows})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/commit_import_students", methods=["POST"])
@admin_required
def commit_import_students():
    data = request.get_json()
    rows = data.get('rows', [])

    if not rows:
        return jsonify({"inserted": 0, "updated": 0, "skipped": 0, "errors": "No rows to import"}), 400

    try:
        houses_res = supabase.table('houses').select('id, name').execute()
        house_map = {h['name'].lower(): h['id'] for h in houses_res.data}

        students_to_upsert = []
        for row in rows:
            house_id = house_map.get(row.get('house', '').lower())
            if not house_id:
                continue # Should be pre-validated, but check again

            students_to_upsert.append({
                "full_name": row.get('full_name'),
                "roll_no": row.get('roll_no') or None, # Handle empty roll_no
                "house_id": house_id,
                "email": row.get('email') or None
            })

        # Supabase upsert will insert or update based on the conflict target (roll_no)
        res = supabase.table('students').upsert(
            students_to_upsert,
            on_conflict='roll_no',
            ignore_duplicates=False # We want to update, not ignore
        ).execute()

        # The response from upsert doesn't directly give counts of inserted/updated
        # For simplicity, we'll return the total number of processed rows.
        # A more complex implementation could query before/after states.
        count = len(res.data)

        return jsonify({"inserted": count, "updated": "N/A", "skipped": len(rows) - count})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Sports & Games Management ---
@app.route("/admin/sports-games")
@admin_required
def manage_sports_games():
    sports = supabase.table('sports').select('*').execute()
    games = supabase.table('games').select('*, sports!inner(name)').execute()
    return render_template("sports_games.html", sports=sports.data, games=games.data)

@app.route("/admin/sports/add", methods=["POST"])
@admin_required
def add_sport():
    try:
        name = request.form.get("name")
        description = request.form.get("description")
        supabase.table('sports').insert({"name": name, "description": description}).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/admin/sports/edit/<int:sport_id>", methods=["POST"])
@admin_required
def edit_sport(sport_id):
    try:
        name = request.form.get("name")
        description = request.form.get("description")
        supabase.table('sports').update({"name": name, "description": description}).eq('id', sport_id).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/admin/sports/delete/<int:sport_id>", methods=["POST"])
@admin_required
def delete_sport(sport_id):
    try:
        supabase.table('sports').delete().eq('id', sport_id).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/admin/games/add", methods=["POST"])
@admin_required
def add_game():
    try:
        title = request.form.get("title")
        sport_id = request.form.get("sport_id")
        venue = request.form.get("venue")
        start_time = request.form.get("start_time")
        supabase.table('games').insert({
            "title": title,
            "sport_id": sport_id,
            "venue": venue,
            "start_time": start_time
        }).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/admin/games/edit/<int:game_id>", methods=["POST"])
@admin_required
def edit_game(game_id):
    try:
        title = request.form.get("title")
        sport_id = request.form.get("sport_id")
        venue = request.form.get("venue")
        start_time = request.form.get("start_time")
        supabase.table('games').update({
            "title": title,
            "sport_id": sport_id,
            "venue": venue,
            "start_time": start_time
        }).eq('id', game_id).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/admin/games/delete/<int:game_id>", methods=["POST"])
@admin_required
def delete_game(game_id):
    try:
        supabase.table('games').delete().eq('id', game_id).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# --- Scoring Rules Management ---
@app.route("/admin/scoring-rules")
@admin_required
def manage_scoring_rules():
    rules = supabase.table('scoring_rules').select('*').execute()
    return render_template("scoring_rules.html", rules=rules.data)

@app.route("/admin/scoring-rules/add", methods=["POST"])
@admin_required
def add_scoring_rule():
    try:
        name = request.form.get("name")
        description = request.form.get("description")
        rule_json = request.form.get("rule_json")
        supabase.table('scoring_rules').insert({
            "name": name,
            "description": description,
            "rule_json": rule_json
        }).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/admin/scoring-rules/edit/<int:rule_id>", methods=["POST"])
@admin_required
def edit_scoring_rule(rule_id):
    try:
        name = request.form.get("name")
        description = request.form.get("description")
        rule_json = request.form.get("rule_json")
        supabase.table('scoring_rules').update({
            "name": name,
            "description": description,
            "rule_json": rule_json
        }).eq('id', rule_id).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/admin/scoring-rules/delete/<int:rule_id>", methods=["POST"])
@admin_required
def delete_scoring_rule(rule_id):
    try:
        supabase.table('scoring_rules').delete().eq('id', rule_id).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# --- Scoring Routes ---
@app.route("/admin/games")
@admin_required
def manage_games():
    games = supabase.table('games').select('*').execute()
    return render_template("games.html", games=games.data)

@app.route("/game/<int:game_id>/scores")
@login_required # Teacher or Admin can view
def manage_game_scores(game_id):
    game = supabase.table('games').select('*').eq('id', game_id).single().execute().data
    participants = supabase.table('participants').select('*, students!inner(full_name, houses!inner(name))').eq('game_id', game_id).execute().data
    houses = supabase.table('houses').select('*').execute().data
    audit_logs = supabase.table('audit_log').select('*').eq('record_id', game_id).eq('table_name', 'scores').execute().data # Simplified

    return render_template("game_scores.html", game=game, participants=participants, houses=houses, audit_logs=audit_logs)

@app.route("/api/scores/individual/<int:game_id>", methods=["POST"])
@login_required # Teacher or Admin
def submit_individual_scores(game_id):
    # Basic permission check
    if not (session.get('is_admin') or session.get('is_teacher')):
        return "Unauthorized", 403

    form_data = request.form
    scores_to_insert = []
    audit_logs_to_insert = []

    i = 0
    while f'student_id_{i}' in form_data:
        student_id = form_data.get(f'student_id_{i}')
        points = form_data.get(f'points_{i}')

        if student_id and points:
            # Get house_id for the student
            student_data = supabase.table('students').select('house_id').eq('id', student_id).single().execute().data

            score_entry = {
                "game_id": game_id,
                "student_id": int(student_id),
                "house_id": student_data['house_id'],
                "points": int(points),
                "type": "individual",
                "recorded_by": session['user']
            }
            scores_to_insert.append(score_entry)

            audit_logs_to_insert.append({
                "action_type": "score_inserted",
                "table_name": "scores",
                "record_id": game_id, # Simplified: linking to game
                "new_value": score_entry,
                "performed_by": session['user']
            })
        i += 1

    if scores_to_insert:
        supabase.table('scores').insert(scores_to_insert).execute()
        supabase.table('audit_log').insert(audit_logs_to_insert).execute()

    return redirect(url_for('manage_game_scores', game_id=game_id))

@app.route("/api/scores/group/<int:game_id>", methods=["POST"])
@login_required # Teacher or Admin
def submit_group_scores(game_id):
    if not (session.get('is_admin') or session.get('is_teacher')):
        return "Unauthorized", 403

    house_id = request.form.get("house_id")
    points = request.form.get("points")

    score_entry = {
        "game_id": game_id,
        "house_id": int(house_id),
        "points": int(points),
        "type": "group",
        "recorded_by": session['user']
    }
    supabase.table('scores').insert(score_entry).execute()

    audit_log_entry = {
        "action_type": "score_inserted_group",
        "table_name": "scores",
        "record_id": game_id,
        "new_value": score_entry,
        "performed_by": session['user']
    }
    supabase.table('audit_log').insert(audit_log_entry).execute()

    return redirect(url_for('manage_game_scores', game_id=game_id))

# --- Data & Visualization Routes ---
@app.route("/leaderboard")
@login_required
def leaderboard():
    return render_template("leaderboard.html")

@app.route("/graphs")
@login_required
def graphs():
    games = supabase.table('games').select('id, title').execute()
    return render_template("graphs.html", games=games.data)

@app.route("/api/leaderboard")
@login_required
def api_leaderboard():
    # More efficient query using a database function (RPC)
    # This assumes a function `get_leaderboard` is created in Supabase
    # For now, we will use a more efficient Python implementation
    scores = supabase.table('scores').select('points, houses!inner(name, color)').execute()

    house_points = {}
    for score in scores.data:
        house_name = score['houses']['name']
        if house_name not in house_points:
            house_points[house_name] = {'points': 0, 'color': score['houses']['color'], 'name': house_name}
        house_points[house_name]['points'] += score['points']

    sorted_leaderboard = sorted(house_points.values(), key=lambda x: x['points'], reverse=True)
    return jsonify(sorted_leaderboard)

@app.route("/api/graphs/cumulative")
@login_required
def api_graphs_cumulative():
    scores = supabase.table('scores').select('points, recorded_at, houses!inner(name)').order('recorded_at', desc=False).execute()

    series = {}
    dates = set()
    house_cumulative_points = {}

    # Initialize houses and dates
    houses = supabase.table('houses').select('name').execute().data
    for house in houses:
        house_name = house['name']
        series[house_name] = []
        house_cumulative_points[house_name] = 0

    # Get all unique dates
    for score in scores.data:
        dates.add(score['recorded_at'].split('T')[0])

    sorted_dates = sorted(list(dates))

    # Calculate cumulative points for each date
    for date in sorted_dates:
        for house_name in house_cumulative_points:
            points_on_date = sum(s['points'] for s in scores.data if s['recorded_at'].split('T')[0] == date and s['houses']['name'] == house_name)
            house_cumulative_points[house_name] += points_on_date
            series[house_name].append(house_cumulative_points[house_name])

    return jsonify({"dates": sorted_dates, "series": series})

@app.route("/api/graphs/by_game")
@login_required
def api_graphs_by_game():
    game_id = request.args.get('game_id')
    if not game_id:
        return jsonify({"error": "game_id is required"}), 400

    scores = supabase.table('scores').select('points, houses!inner(name)').eq('game_id', game_id).execute()

    breakdown = {}
    for score in scores.data:
        house_name = score['houses']['name']
        if house_name not in breakdown:
            breakdown[house_name] = 0
        breakdown[house_name] += score['points']

    response = [{"house": name, "points": pts} for name, pts in breakdown.items()]
    return jsonify({"game_id": game_id, "breakdown": response})

if __name__ == "__main__":
    app.run(debug=True)
