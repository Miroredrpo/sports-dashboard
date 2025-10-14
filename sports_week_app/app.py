import os
import csv
import io
from functools import wraps
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from supabase import create_client, Client
from dotenv import load_dotenv
from postgrest.exceptions import APIError

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY")

supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# --- Role Checking Functions ---
def is_admin(user_id):
    try:
        res = supabase.table('admins').select('user_id').eq('user_id', user_id).execute().data
        return len(res) > 0
    except Exception as e:
        print(e)
        return False

def is_teacher(user_id):
    try:
        res = supabase.table('teachers').select('user_id').eq('user_id', user_id).execute().data
        return len(res) > 0
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
            flash("A verification link has been sent to your email. Please verify your account before logging in.", "info")
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
    houses = supabase.table('houses').select('*').execute().data
    return render_template("houses.html", houses=houses)

@app.route("/admin/houses/add", methods=["POST"])
@admin_required
def add_house():
    try:
        name = request.form.get("name")
        color = request.form.get("color")
        new_house = supabase.table('houses').insert({"name": name, "color": color}).execute().data[0]
        supabase.table('audit_log').insert({
            "action_type": "add_house",
            "table_name": "houses",
            "record_id": new_house['id'],
            "new_value": {"name": name, "color": color},
            "performed_by": session['user']
        }).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/admin/houses/edit/<int:house_id>", methods=["POST"])
@admin_required
def edit_house(house_id):
    try:
        name = request.form.get("name")
        color = request.form.get("color")
        old_house = supabase.table('houses').select('*').eq('id', house_id).single().execute().data
        supabase.table('houses').update({"name": name, "color": color}).eq('id', house_id).execute()
        supabase.table('audit_log').insert({
            "action_type": "edit_house",
            "table_name": "houses",
            "record_id": house_id,
            "old_value": old_house,
            "new_value": {"name": name, "color": color},
            "performed_by": session['user']
        }).execute()
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

# --- Student Management ---
@app.route("/admin/students")
@admin_required
def manage_students():
    students = supabase.table('students').select('*, houses!inner(name)').execute().data
    houses = supabase.table('houses').select('*').execute().data
    return render_template("manage_students.html", students=students, houses=houses)

@app.route("/admin/students/add", methods=["POST"])
@admin_required
def add_student():
    try:
        supabase.table('students').insert({
            "full_name": request.form.get("full_name"),
            "roll_no": request.form.get("roll_no") or None,
            "house_id": request.form.get("house_id"),
            "email": request.form.get("email") or None
        }).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/admin/students/edit/<int:student_id>", methods=["POST"])
@admin_required
def edit_student(student_id):
    try:
        supabase.table('students').update({
            "full_name": request.form.get("full_name"),
            "roll_no": request.form.get("roll_no") or None,
            "house_id": request.form.get("house_id"),
            "email": request.form.get("email") or None
        }).eq('id', student_id).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/admin/students/delete/<int:student_id>", methods=["POST"])
@admin_required
def delete_student(student_id):
    try:
        supabase.table('students').delete().eq('id', student_id).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

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
        houses_res = supabase.table('houses').select('id, name').execute().data
        house_map = {h['name'].lower(): h['id'] for h in houses_res}

        students_res = supabase.table('students').select('roll_no').execute().data
        existing_roll_nos = {s['roll_no'] for s in students_res if s['roll_no']}

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
        houses_res = supabase.table('houses').select('id, name').execute().data
        house_map = {h['name'].lower(): h['id'] for h in houses_res}

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
    sports = supabase.table('sports').select('*').execute().data
    events = supabase.table('events').select('*, sport:sports!inner(name)').execute().data
    return render_template("manage_events.html", sports=sports, events=events)

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

@app.route("/admin/events/add", methods=["POST"])
@admin_required
def add_event():
    try:
        title = request.form.get("title")
        sport_id = request.form.get("sport_id")
        venue = request.form.get("venue")
        start_time = request.form.get("start_time")
        scoring_model = request.form.get("scoring_model")
        new_event = supabase.table('events').insert({
            "title": title,
            "sport_id": sport_id,
            "venue": venue,
            "start_time": start_time,
            "scoring_model": scoring_model
        }).execute().data[0]
        supabase.table('audit_log').insert({
            "action_type": "add_event",
            "table_name": "events",
            "record_id": new_event['id'],
            "new_value": {"title": title, "sport_id": sport_id, "scoring_model": scoring_model},
            "performed_by": session['user']
        }).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/admin/events/edit/<int:event_id>", methods=["POST"])
@admin_required
def edit_event(event_id):
    try:
        title = request.form.get("title")
        sport_id = request.form.get("sport_id")
        venue = request.form.get("venue")
        start_time = request.form.get("start_time")
        scoring_model = request.form.get("scoring_model")
        supabase.table('events').update({
            "title": title,
            "sport_id": sport_id,
            "venue": venue,
            "start_time": start_time,
            "scoring_model": scoring_model
        }).eq('id', event_id).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/admin/events/delete/<int:event_id>", methods=["POST"])
@admin_required
def delete_event(event_id):
    try:
        supabase.table('events').delete().eq('id', event_id).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# --- Winners Page ---
@app.route("/winners")
def winners():
    winners_data = supabase.table('winners').select('*, sports!inner(name), houses!left(name)').execute().data
    return render_template("winners.html", winners=winners_data)

@app.route("/admin/winners")
@admin_required
def manage_winners():
    winners_data = supabase.table('winners').select('*, sports!inner(name), houses!left(name)').execute().data
    sports = supabase.table('sports').select('id, name').execute().data
    houses = supabase.table('houses').select('id, name').execute().data
    return render_template("manage_winners.html", winners=winners_data, sports=sports, houses=houses)

@app.route("/admin/winners/add", methods=["POST"])
@admin_required
def add_winner():
    try:
        sport_id = request.form.get("sport_id")
        house_id = request.form.get("house_id")
        status = request.form.get("status")

        # Upsert logic: update if sport_id exists, else insert
        supabase.table('winners').upsert({
            "sport_id": sport_id,
            "house_id": house_id if house_id else None,
            "status": status
        }, on_conflict='sport_id').execute()

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/admin/winners/delete/<int:winner_id>", methods=["POST"])
@admin_required
def delete_winner(winner_id):
    try:
        supabase.table('winners').delete().eq('id', winner_id).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# --- New Competition Workflow ---
@app.route("/update-scores")
@admin_required
def update_scores_dashboard():
    sports = supabase.table('sports').select('*').execute().data
    return render_template("update_score_dashboard.html", sports=sports)

@app.route("/competitions/list/<int:sport_id>")
@admin_required
def list_competitions(sport_id):
    sport = supabase.table('sports').select('*').eq('id', sport_id).single().execute().data
    competitions = supabase.table('competitions').select('*, events!inner(*)').eq('events.sport_id', sport_id).execute().data
    return render_template("list_competitions.html", sport=sport, competitions=competitions)

@app.route("/competitions/setup/<int:sport_id>")
@admin_required
def setup_competition(sport_id):
    sport = supabase.table('sports').select('*').eq('id', sport_id).single().execute().data
    houses = supabase.table('houses').select('*').execute().data
    students = supabase.table('students').select('*, houses!inner(name)').execute().data
    return render_template("competition_setup.html", sport=sport, houses=houses, students=students)

@app.route("/competitions/create/individual/<int:sport_id>", methods=["POST"])
@admin_required
def create_individual_competition(sport_id):
    match_type = request.form.get("match_type")
    sport = supabase.table('sports').select('name').eq('id', sport_id).single().execute().data

    if match_type == '1v1':
        p1_id = request.form.get("p1_1v1")
        p2_id = request.form.get("p2_1v1")
        student_ids = [p1_id, p2_id]
        students = supabase.table('students').select('full_name, houses!inner(name)').in_('id', student_ids).execute().data
        s1 = next(s for s in students if s['id'] == int(p1_id))
        s2 = next(s for s in students if s['id'] == int(p2_id))
        title = f"{s1['houses']['name']} vs {s2['houses']['name']} ({s1['full_name']} vs {s2['full_name']})"
    else: # 2v2
        p1_t1 = request.form.get("p1_2v2_t1")
        p2_t1 = request.form.get("p2_2v2_t1")
        p1_t2 = request.form.get("p1_2v2_t2")
        p2_t2 = request.form.get("p2_2v2_t2")
        student_ids = [p1_t1, p2_t1, p1_t2, p2_t2]
        title = f"2v2 Individual Competition for {sport['name']}" # Simplified for now

    event = supabase.table('events').insert({
        "sport_id": sport_id,
        "title": title,
        "scoring_model": "points"
    }).execute().data[0]

    competition = supabase.table('competitions').insert({
        "event_id": event['id'],
        "type": "individual"
    }).execute().data[0]

    if match_type == '1v1':
        participants = [{"competition_id": competition['id'], "student_id": sid} for sid in student_ids]
    else: # 2v2
        participants = [
            {"competition_id": competition['id'], "student_id": p1_t1, "team_number": 1},
            {"competition_id": competition['id'], "student_id": p2_t1, "team_number": 1},
            {"competition_id": competition['id'], "student_id": p1_t2, "team_number": 2},
            {"competition_id": competition['id'], "student_id": p2_t2, "team_number": 2},
        ]

    supabase.table('competition_students').insert(participants).execute()

    supabase.table('audit_log').insert({
        "action_type": "create_competition",
        "table_name": "competitions",
        "record_id": competition['id'],
        "new_value": {"type": "individual", "match_type": match_type, "event_id": event['id'], "participants": student_ids},
        "performed_by": session['user']
    }).execute()

    return redirect(url_for('manage_competition', competition_id=competition['id']))

@app.route("/competitions/create/group/<int:sport_id>", methods=["POST"])
@admin_required
def create_group_competition(sport_id):
    house1_id = int(request.form.get("house1_id"))
    house2_id = int(request.form.get("house2_id"))

    if house1_id == house2_id:
        return "Cannot create a competition between the same house", 400

    # Check for existing competition
    try:
        existing = supabase.rpc('get_competition_between_houses', {'house1_id_param': house1_id, 'house2_id_param': house2_id, 'sport_id_param': sport_id}).execute().data
        if existing:
            return redirect(url_for('manage_competition', competition_id=existing[0]['id']))
    except APIError as e:
        print(f"Could not check for existing competitions. This is expected if the DB function is not created yet. Error: {e}")

    sport = supabase.table('sports').select('name').eq('id', sport_id).single().execute().data
    houses = supabase.table('houses').select('id, name').in_('id', [house1_id, house2_id]).execute().data
    house_names = {h['id']: h['name'] for h in houses}

    # For simplicity, we'll create a new 'event' for each competition
    event = supabase.table('events').insert({
        "sport_id": sport_id,
        "title": f"{sport['name']}: {house_names[house1_id]} vs {house_names[house2_id]}",
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

    supabase.table('audit_log').insert({
        "action_type": "create_competition",
        "table_name": "competitions",
        "record_id": competition['id'],
        "new_value": {"type": "group", "event_id": event['id'], "houses": [house1_id, house2_id]},
        "performed_by": session['user']
    }).execute()

    return redirect(url_for('manage_competition', competition_id=competition['id']))

@app.route("/competitions/manage/<int:competition_id>")
@admin_required
def manage_competition(competition_id):
    try:
        competition = supabase.table('competitions').select('*, events!inner(*)').eq('id', competition_id).single().execute().data
    except APIError:
        return "Competition not found", 404

    participants = []
    if competition['type'] == 'group':
        group_participants = supabase.table('competition_houses').select('houses!inner(id, name)').eq('competition_id', competition_id).execute().data
        participants = [p['houses'] for p in group_participants]
        competition['houses'] = participants # For display
    elif competition['type'] == 'individual':
        individual_participants = supabase.table('competition_students').select('students!inner(id, full_name)').eq('competition_id', competition_id).execute().data
        participants = [p['students'] for p in individual_participants]

    rounds_res = supabase.table('competition_rounds').select('*, scores!left(*)').eq('competition_id', competition_id).order('round_number').execute().data

    for round_item in rounds_res:
        for score in round_item['scores']:
            if score.get('house_id'):
                score['houses'] = supabase.table('houses').select('name').eq('id', score['house_id']).single().execute().data
            if score.get('student_id'):
                score['students'] = supabase.table('students').select('full_name').eq('id', score['student_id']).single().execute().data

    return render_template("manage_competition.html", competition=competition, rounds=rounds_res, participants=participants)

@app.route("/competitions/rounds/add/<int:competition_id>", methods=["POST"])
@admin_required
def add_competition_round(competition_id):
    try:
        competition = supabase.table('competitions').select('type').eq('id', competition_id).single().execute().data
    except APIError:
        return "Competition not found", 404

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
        houses = supabase.table('competition_houses').select('house_id').eq('competition_id', competition_id).execute().data
        for house in houses:
            points = request.form.get(f"points_{house['house_id']}")
            if points:
                scores_to_insert.append({"round_id": new_round['id'], "house_id": house['house_id'], "points": int(points)})
    else: # Individual
        students = supabase.table('competition_students').select('student_id').eq('competition_id', competition_id).execute().data
        for student in students:
            points = request.form.get(f"points_{student['student_id']}")
            if points:
                scores_to_insert.append({"round_id": new_round['id'], "student_id": student['student_id'], "points": int(points)})

    if scores_to_insert:
        supabase.table('scores').insert(scores_to_insert).execute()

    supabase.table('audit_log').insert({
        "action_type": "add_round",
        "table_name": "competition_rounds",
        "record_id": new_round['id'],
        "new_value": {"competition_id": competition_id, "round": next_round_number, "scores": scores_to_insert},
        "performed_by": session['user']
    }).execute()

    return redirect(url_for('manage_competition', competition_id=competition_id))

@app.route("/competitions/rounds/edit/<int:round_id>", methods=["POST"])
@admin_required
def edit_competition_round(round_id):
    details = request.form.get("details")

    # Update round details
    supabase.table('competition_rounds').update({"details": details}).eq('id', round_id).execute()

    # Update scores
    scores = supabase.table('scores').select('id').eq('round_id', round_id).execute().data
    for score in scores:
        points = request.form.get(f"points_{score['id']}")
        if points:
            supabase.table('scores').update({"points": int(points)}).eq('id', score['id']).execute()

    # Audit log
    supabase.table('audit_log').insert({
        "action_type": "edit_round",
        "table_name": "competition_rounds",
        "record_id": round_id,
        "new_value": {"details": details, "updated_scores": True}, # Simplified
        "performed_by": session['user']
    }).execute()

    # Return the updated data to the client
    updated_round = supabase.table('competition_rounds').select('*, scores!left(*)').eq('id', round_id).single().execute().data
    for score in updated_round.get('scores', []):
        if score.get('house_id'):
            score['houses'] = supabase.table('houses').select('name').eq('id', score['house_id']).single().execute().data
        if score.get('student_id'):
            score['students'] = supabase.table('students').select('full_name').eq('id', score['student_id']).single().execute().data

    return jsonify({"success": True, "round": updated_round})

@app.route("/competitions/rounds/delete/<int:round_id>", methods=["POST"])
@admin_required
def delete_competition_round(round_id):
    competition_id = supabase.table('competition_rounds').select('competition_id').eq('id', round_id).single().execute().data['competition_id']

    # Deleting a round will cascade and delete associated scores due to DB constraints
    supabase.table('competition_rounds').delete().eq('id', round_id).execute()

    # Audit log
    supabase.table('audit_log').insert({
        "action_type": "delete_round",
        "table_name": "competition_rounds",
        "record_id": round_id,
        "old_value": {"round_id": round_id},
        "performed_by": session['user']
    }).execute()

    return redirect(url_for('manage_competition', competition_id=competition_id))

# --- Data & Visualization Routes ---
@app.route("/leaderboard")
@login_required
def leaderboard():
    sports = supabase.table('sports').select('id, name').execute().data
    return render_template("leaderboard.html", sports=sports)

@app.route("/graphs")
@login_required
def graphs():
    events = supabase.table('events').select('id, title, sport:sports!inner(description)').execute().data
    return render_template("graphs.html", games=events) # Re-using 'games' variable in template

@app.route("/api/leaderboard")
@login_required
def api_leaderboard():
    sport_id = request.args.get('sport_id', 'all')

    # Base query for all scores, joining through to sport_id for filtering
    query = supabase.table('scores').select('points, house_id, student_id, competition_rounds!inner(competitions!inner(events!inner(sport_id)))')

    if sport_id != 'all':
        query = query.eq('competition_rounds.competitions.events.sport_id', sport_id)

    scores = query.execute().data

    # Pre-fetch all houses and students to avoid N+1 queries
    all_houses = {h['id']: h for h in supabase.table('houses').select('id, name, color').execute().data}
    all_students = {s['id']: s for s in supabase.table('students').select('id, house_id').execute().data}

    house_points = {h['name']: {'points': 0, 'color': h['color'], 'name': h['name']} for h in all_houses.values()}

    for score in scores:
        house_id = None
        if score['house_id']:
            house_id = score['house_id']
        elif score['student_id'] and score['student_id'] in all_students:
            house_id = all_students[score['student_id']]['house_id']

        if house_id and house_id in all_houses:
            house_name = all_houses[house_id]['name']
            if house_name in house_points:
                house_points[house_name]['points'] += score['points']

    sorted_leaderboard = sorted(house_points.values(), key=lambda x: x['points'], reverse=True)
    return jsonify(sorted_leaderboard)

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

    scores = supabase.table('scores').select('points, houses!inner(name)').in_('round_id', round_ids).execute().data

    breakdown = {}
    for score in scores:
        if score.get('houses'):
            house_name = score['houses']['name']
            if house_name not in breakdown:
                breakdown[house_name] = 0
            breakdown[house_name] += score['points']

    response = [{"house": name, "points": pts} for name, pts in breakdown.items()]
    return jsonify({"event_id": event_id, "breakdown": response})

if __name__ == "__main__":
    app.run(debug=True)
