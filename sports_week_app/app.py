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

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        try:
            supabase.auth.sign_up({"email": email, "password": password})
            return redirect(url_for('login'))
        except Exception as e:
            return render_template("signup.html", error=str(e))
    return render_template("signup.html")

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

@app.route("/admin/houses/delete/<int:house_id>", methods=["GET", "POST"])
@admin_required
def delete_house(house_id):
    try:
        supabase.table('houses').delete().eq('id', house_id).execute()
        if request.method == 'POST':
            return jsonify({"success": True})
        return redirect(url_for('manage_houses'))
    except Exception as e:
        if request.method == 'POST':
            return jsonify({"success": False, "error": str(e)}), 500
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

# --- Event Management (Unified) ---
@app.route("/admin/events")
@admin_required
def manage_events():
    sports = supabase.table('sports').select('*').execute()
    events = supabase.table('events').select('*, sport:sports!inner(name)').execute()
    return render_template("manage_events.html", sports=sports.data, events=events.data)

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

@app.route("/admin/events/add", methods=["POST"])
@admin_required
def add_event():
    try:
        title = request.form.get("title")
        sport_id = request.form.get("sport_id")
        venue = request.form.get("venue")
        start_time = request.form.get("start_time")
        scoring_model = request.form.get("scoring_model")
        supabase.table('events').insert({
            "title": title,
            "sport_id": sport_id,
            "venue": venue,
            "start_time": start_time,
            "scoring_model": scoring_model
        }).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# --- New Competition Workflow ---
@app.route("/update-scores")
@login_required
def update_scores_dashboard():
    sports = supabase.table('sports').select('*').execute()
    return render_template("update_score_dashboard.html", sports=sports.data)

@app.route("/competitions/setup/<int:sport_id>")
@login_required
def setup_competition(sport_id):
    sport = supabase.table('sports').select('*').eq('id', sport_id).single().execute().data
    houses = supabase.table('houses').select('*').execute().data
    students = supabase.table('students').select('*, houses!inner(name)').execute().data
    return render_template("competition_setup.html", sport=sport, houses=houses.data, students=students)

@app.route("/competitions/create/individual/<int:sport_id>", methods=["POST"])
@login_required
def create_individual_competition(sport_id):
    student_ids = request.form.getlist("student_ids")

    event = supabase.table('events').insert({
        "sport_id": sport_id,
        "title": f"Individual Competition for Sport ID {sport_id}",
        "scoring_model": "points"
    }).execute().data[0]

    competition = supabase.table('competitions').insert({
        "event_id": event['id'],
        "type": "individual"
    }).execute().data[0]

    supabase.table('competition_students').insert(
        [{"competition_id": competition['id'], "student_id": sid} for sid in student_ids]
    ).execute()

    return redirect(url_for('manage_competition', competition_id=competition['id']))

@app.route("/competitions/create/group/<int:sport_id>", methods=["POST"])
@login_required
def create_group_competition(sport_id):
    house1_id = request.form.get("house1_id")
    house2_id = request.form.get("house2_id")

    # For simplicity, we'll create a new 'event' for each competition
    event = supabase.table('events').insert({
        "sport_id": sport_id,
        "title": f"Competition for Sport ID {sport_id}",
        "scoring_model": "victory"
    }).execute().data[0]

    competition = supabase.table('competitions').insert({
        "event_id": event['id'],
        "type": "group"
    }).execute().data[0]

    supabase.table('competition_houses').insert([
        {"competition_id": competition['id'], "house_id": house1_id},
        {"competition_id": competition['id'], "house_id": house2_id}
    ]).execute()

    return redirect(url_for('manage_competition', competition_id=competition['id']))

@app.route("/competitions/manage/<int:competition_id>")
@login_required
def manage_competition(competition_id):
    competition = supabase.table('competitions').select('*, events!inner(*), houses!inner(*)').eq('id', competition_id).single().execute().data

    rounds_res = supabase.table('competition_rounds').select('*, scores!left(*)').eq('competition_id', competition_id).order('round_number').execute().data

    participants = []
    if competition['type'] == 'individual':
        participants = supabase.table('competition_students').select('students!inner(id, full_name)').eq('competition_id', competition_id).execute().data
        participants = [p['students'] for p in participants]

    for round_item in rounds_res:
        round_item['scores'] = [s for s in round_item['scores']]
        for score in round_item['scores']:
            if score.get('house_id'):
                score['houses'] = supabase.table('houses').select('name').eq('id', score['house_id']).single().execute().data
            if score.get('student_id'):
                score['students'] = supabase.table('students').select('full_name').eq('id', score['student_id']).single().execute().data

    return render_template("manage_competition.html", competition=competition, rounds=rounds_res, participants=participants)

@app.route("/competitions/rounds/add/<int:competition_id>", methods=["POST"])
@login_required
def add_competition_round(competition_id):
    competition = supabase.table('competitions').select('type, houses!inner(id), competition_students!inner(student_id)').eq('id', competition_id).single().execute().data
    details = request.form.get("details")

    rounds = supabase.table('competition_rounds').select('round_number').eq('competition_id', competition_id).execute().data
    next_round_number = len(rounds) + 1

    new_round = supabase.table('competition_rounds').insert({
        "competition_id": competition_id,
        "round_number": next_round_number,
        "details": details
    }).execute().data[0]

    scores_to_insert = []
    if competition['type'] == 'group':
        for house in competition['houses']:
            points = request.form.get(f"points_{house['id']}")
            if points:
                scores_to_insert.append({"round_id": new_round['id'], "house_id": house['id'], "points": int(points)})
    else: # Individual
        for student in competition['competition_students']:
            points = request.form.get(f"points_{student['student_id']}")
            if points:
                scores_to_insert.append({"round_id": new_round['id'], "student_id": student['student_id'], "points": int(points)})

    if scores_to_insert:
        supabase.table('scores').insert(scores_to_insert).execute()

    return redirect(url_for('manage_competition', competition_id=competition_id))

# --- Data & Visualization Routes ---
@app.route("/leaderboard")
@login_required
def leaderboard():
    return render_template("leaderboard.html")

@app.route("/graphs")
@login_required
def graphs():
    events = supabase.table('events').select('id, title').execute()
    return render_template("graphs.html", games=events.data) # Re-using 'games' variable in template

@app.route("/api/leaderboard")
@login_required
def api_leaderboard():
    scores = supabase.table('scores').select('points, houses!inner(name, color)').execute()

    house_points = {}
    all_houses = supabase.table('houses').select('name, color').execute().data
    for house in all_houses:
        house_points[house['name']] = {'points': 0, 'color': house['color'], 'name': house['name']}

    for score in scores.data:
        if score.get('houses'):
            house_name = score['houses']['name']
            if house_name in house_points:
                house_points[house_name]['points'] += score['points']

    sorted_leaderboard = sorted(house_points.values(), key=lambda x: x['points'], reverse=True)
    return jsonify(sorted_leaderboard)

@app.route("/api/graphs/cumulative")
@login_required
def api_graphs_cumulative():
    scores = supabase.table('scores').select('recorded_at, points, houses!inner(name)').order('recorded_at', desc=False).execute()

    series = {}
    dates = set()
    house_cumulative_points = {}

    houses = supabase.table('houses').select('name').execute().data
    for house in houses:
        house_name = house['name']
        series[house_name] = []
        house_cumulative_points[house_name] = 0

    for score in scores.data:
        if score.get('houses'):
            dates.add(score['recorded_at'].split('T')[0])

    sorted_dates = sorted(list(dates))

    for date in sorted_dates:
        for house_name in house_cumulative_points:
            points_on_date = sum(s['points'] for s in scores.data if s.get('houses') and s['recorded_at'].split('T')[0] == date and s['houses']['name'] == house_name)
            house_cumulative_points[house_name] += points_on_date
            series[house_name].append(house_cumulative_points[house_name])

    return jsonify({"dates": sorted_dates, "series": series})

@app.route("/api/graphs/by_event")
@login_required
def api_graphs_by_event():
    event_id = request.args.get('event_id')
    if not event_id:
        return jsonify({"error": "event_id is required"}), 400

    competitions = supabase.table('competitions').select('id').eq('event_id', event_id).execute().data
    competition_ids = [c['id'] for c in competitions]

    rounds = supabase.table('competition_rounds').select('id').in_('competition_id', competition_ids).execute().data
    round_ids = [r['id'] for r in rounds]

    scores = supabase.table('scores').select('points, houses!inner(name)').in_('round_id', round_ids).execute()

    breakdown = {}
    for score in scores.data:
        if score.get('houses'):
            house_name = score['houses']['name']
            if house_name not in breakdown:
                breakdown[house_name] = 0
            breakdown[house_name] += score['points']

    response = [{"house": name, "points": pts} for name, pts in breakdown.items()]
    return jsonify({"event_id": event_id, "breakdown": response})

if __name__ == "__main__":
    app.run(debug=True)
