"""
Skill Navigator — AI-Powered Job Matching System
================================================
HOW TO RUN:
  1. Place this file at your project ROOT (e.g. SkillNavigator/app.py)
  2. Run:  python app.py
  3. Open: http://localhost:5000

Company login: admin / 1234
"""
import os, sys, sqlite3, hashlib, json
from datetime import datetime
from functools import wraps

import pandas as pd
import xml.etree.ElementTree as ET
from flask import (Flask, render_template, request, redirect,
                   url_for, flash, session, jsonify)

# ── locate project root regardless of where app.py lives ─────────────────────
HERE = os.path.dirname(os.path.abspath(__file__))
# If app.py is inside a subfolder like backend/, climb up to find templates/
if not os.path.isdir(os.path.join(HERE, 'templates')):
    HERE = os.path.dirname(HERE)          # go up one level

TEMPLATE_DIR = os.path.join(HERE, 'templates')
STATIC_DIR   = os.path.join(HERE, 'static')
DATA_DIR     = os.path.join(HERE, 'Data')
UPLOAD_DIR   = os.path.join(HERE, 'uploads')
DB_PATH      = os.path.join(HERE, 'students.db')

for d in [DATA_DIR, UPLOAD_DIR, STATIC_DIR]:
    os.makedirs(d, exist_ok=True)

# ── Optional email ────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(HERE, '.env'))
except ImportError:
    pass

try:
    from backend.utils import send_email as _send
    def send_email(to, subj, body, attach=None):
        try: _send(to, subj, body, attach)
        except Exception as e: print(f"[email skip] {e}")
except Exception:
    def send_email(to, subj, body, attach=None):
        print(f"[EMAIL] to={to} | {subj}")

# ═════════════════════════════════════════════════════════════════════════════
app = Flask(__name__,
            template_folder=TEMPLATE_DIR,
            static_folder=STATIC_DIR)
app.secret_key = os.getenv('SECRET_KEY', 'skillnav_secret_2026_xK9mP')

COMPANY_CREDS = {'admin': hashlib.sha256('1234'.encode()).hexdigest()}

# ═════════════════════════════════════════════════════════════════════════════
# DATABASE
# ═════════════════════════════════════════════════════════════════════════════
def get_db():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT DEFAULT '',
            email TEXT UNIQUE,
            skills TEXT DEFAULT '',
            goal TEXT DEFAULT '',
            niche TEXT DEFAULT '',
            role_mode INTEGER DEFAULT 0,
            resume_file TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            job_title TEXT DEFAULT '',
            company TEXT DEFAULT '',
            location TEXT DEFAULT '',
            package TEXT DEFAULT '',
            applied_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS saved_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            job_title TEXT DEFAULT '',
            company TEXT DEFAULT '',
            UNIQUE(username, job_title, company)
        );
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT DEFAULT '',
            action TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );
        """)

def hp(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def db_get_user(username):
    with get_db() as db:
        r = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        return dict(r) if r else None

def db_create_user(username, password, name, email, skills,
                   goal='', niche='', role_mode=0, resume=None):
    try:
        with get_db() as db:
            db.execute(
                "INSERT INTO users(username,password,name,email,skills,"
                "goal,niche,role_mode,resume_file) VALUES(?,?,?,?,?,?,?,?,?)",
                (username.strip(), hp(password), name.strip(), email.strip(),
                 skills.strip(), goal.strip(), niche.strip(),
                 int(role_mode), resume or '')
            )
        return True, None
    except sqlite3.IntegrityError as e:
        msg = ("Username already taken."
               if 'username' in str(e) else "Email already registered.")
        return False, msg

def db_update_user(username, name, skills, goal, niche):
    with get_db() as db:
        db.execute(
            "UPDATE users SET name=?,skills=?,goal=?,niche=? WHERE username=?",
            (name, skills, goal, niche, username))

def db_log(username, action):
    with get_db() as db:
        db.execute("INSERT INTO activity_log(username,action) VALUES(?,?)",
                   (username, action))

def db_activity(username, limit=40):
    with get_db() as db:
        rows = db.execute(
            "SELECT action,created_at FROM activity_log "
            "WHERE username=? ORDER BY id DESC LIMIT ?",
            (username, limit)).fetchall()
        return [dict(r) for r in rows]

def db_log_apply(username, title, company, location, package):
    with get_db() as db:
        db.execute(
            "INSERT INTO applications(username,job_title,company,location,package)"
            " VALUES(?,?,?,?,?)",
            (username, title, company, location, package))

def db_my_apps(username):
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM applications WHERE username=? ORDER BY applied_at DESC",
            (username,)).fetchall()
        return [dict(r) for r in rows]

def db_app_count(username):
    with get_db() as db:
        return db.execute(
            "SELECT COUNT(*) FROM applications WHERE username=?",
            (username,)).fetchone()[0]

def db_total_apps():
    with get_db() as db:
        return db.execute("SELECT COUNT(*) FROM applications").fetchone()[0]

def db_user_count():
    with get_db() as db:
        return db.execute("SELECT COUNT(*) FROM users").fetchone()[0]

def db_save(username, title, company):
    try:
        with get_db() as db:
            db.execute(
                "INSERT OR IGNORE INTO saved_jobs(username,job_title,company)"
                " VALUES(?,?,?)",
                (username, title, company))
        return True
    except Exception:
        return False

def db_unsave(username, title, company):
    with get_db() as db:
        db.execute(
            "DELETE FROM saved_jobs WHERE username=? AND job_title=? AND company=?",
            (username, title, company))

def db_saved(username):
    with get_db() as db:
        rows = db.execute(
            "SELECT job_title,company FROM saved_jobs WHERE username=?",
            (username,)).fetchall()
        return [(r['job_title'], r['company']) for r in rows]

# ═════════════════════════════════════════════════════════════════════════════
# JOB DATA
# ═════════════════════════════════════════════════════════════════════════════
def load_jobs():
    path = os.path.join(DATA_DIR, 'JobList.xlsx')
    if not os.path.exists(path):
        return []
    df = pd.read_excel(path).fillna('')
    recs = df.to_dict('records')
    for i, r in enumerate(recs):
        r['id'] = int(r.get('Job id', i + 1))
    return recs

def load_jobskills():
    path = os.path.join(DATA_DIR, 'Jobskills.xlsx')
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_excel(path).fillna('')

def load_xml_jobs():
    path = os.path.join(DATA_DIR, 'jobList.xml')
    if not os.path.exists(path):
        return []
    jobs = []
    for i, job in enumerate(ET.parse(path).getroot().findall('job')):
        jobs.append({
            'Job Title':       job.findtext('title', ''),
            'Company':         job.findtext('company', ''),
            'Package':         job.findtext('package', ''),
            'Location':        job.findtext('location', ''),
            'Skills Required': job.findtext('skills', ''),
            'Email':           job.findtext('email', 'careers@company.com'),
            'id': f"x{i}"
        })
    return jobs

def all_skills():
    df = load_jobskills()
    s = set()
    for v in df.get('Skills Required', pd.Series([])):
        for sk in str(v).split(','):
            t = sk.strip()
            if t:
                s.add(t)
    return sorted(s)

def compute_match(user_set, job_skills_str):
    job_set = {s.strip().lower()
               for s in str(job_skills_str).split(',') if s.strip()}
    if not job_set:
        return 0, []
    matched = user_set & job_set
    missing = sorted(job_set - user_set)
    return round(len(matched) / len(job_set) * 100), missing

def match_jobs(skills_str, threshold=50):
    user_set = {s.strip().lower()
                for s in skills_str.split(',') if s.strip()}
    if not user_set:
        return []
    js = load_jobskills()
    titles = set()
    for _, row in js.iterrows():
        pct, _ = compute_match(user_set, row.get('Skills Required', ''))
        if pct >= threshold:
            titles.add(str(row['Job Title']).strip())
    results = []
    for job in (load_jobs() + load_xml_jobs()):
        if job['Job Title'].strip() in titles:
            pct, missing = compute_match(user_set, job.get('Skills Required', ''))
            j = dict(job)
            j['match_pct']     = pct
            j['missing_skills'] = missing
            results.append(j)
    results.sort(key=lambda x: x['match_pct'], reverse=True)
    return results

def skill_gap(skills_str, top=10):
    user_set = {s.strip().lower()
                for s in skills_str.split(',') if s.strip()}
    counter = {}
    for _, row in load_jobskills().iterrows():
        _, missing = compute_match(user_set, row.get('Skills Required', ''))
        for s in missing:
            counter[s] = counter.get(s, 0) + 1
    return sorted(counter.items(), key=lambda x: x[1], reverse=True)[:top]

# ═════════════════════════════════════════════════════════════════════════════
# SESSION HELPERS
# ═════════════════════════════════════════════════════════════════════════════
def notif(msg, title="Notification"):
    n = session.get('notifications', [])
    n.insert(0, {
        "title":   title,
        "content": msg,
        "time":    datetime.now().strftime("%d %b %Y, %I:%M %p")
    })
    session['notifications'] = n[:20]

def login_required(f):
    @wraps(f)
    def w(*a, **kw):
        if 'username' not in session:
            flash("Please log in first.", "error")
            return redirect(url_for('login_page'))
        return f(*a, **kw)
    return w

def company_required(f):
    @wraps(f)
    def w(*a, **kw):
        if session.get('role') != 'company':
            flash("Company access only.", "error")
            return redirect(url_for('home'))
        return f(*a, **kw)
    return w

# ═════════════════════════════════════════════════════════════════════════════
LOCATIONS  = ['Bangalore','Hyderabad','Mumbai','Delhi','Pune',
              'Chennai','Gurgaon','Noida','Remote']
PACKAGES   = ['8 to 12 lakhs','10 to 15 lakhs','12 to 15 lakhs',
              '12 to 18 lakhs','15 to 20 lakhs','20 to 30 lakhs','30+ lakhs']
JOB_TITLES = ['AI Engineer','Backend Developer','Big Data Engineer',
              'Blockchain Developer','Cloud Engineer','Cyber Security Analyst',
              'Data Engineer','Data Scientist','Database Administrator',
              'DevOps Engineer','Embedded Engineer','Frontend Developer',
              'Full Stack Developer','Game Developer','Machine Learning Engineer',
              'Mobile App Developer','Network Engineer','NLP Engineer',
              'QA Engineer','Site Reliability Engineer',
              'Software Engineer','System Analyst']

# ═════════════════════════════════════════════════════════════════════════════
# ROUTES
# ═════════════════════════════════════════════════════════════════════════════
@app.route('/')
def home():
    try:
        job_count  = len(load_jobs())
        user_count = db_user_count()
        app_count  = db_total_apps()
    except Exception:
        job_count = user_count = app_count = 0
    return render_template('home.html',
                           job_count=job_count,
                           user_count=user_count,
                           app_count=app_count)

@app.route('/login')
def login_page():
    if 'username' in session:
        return redirect(url_for('company_dashboard')
                        if session.get('role') == 'company'
                        else url_for('dashboard'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        u  = request.form.get('username', '').strip()
        pw = request.form.get('password', '')
        n  = request.form.get('name', '').strip()
        em = request.form.get('email', '').strip()
        sk = request.form.get('skills', '').strip()
        go = request.form.get('goal', '').strip()
        ni = request.form.get('niche', '').strip()
        rm = request.form.get('roleOrSkills') == 'role'

        if not all([u, pw, n, em]):
            flash("All required fields must be filled.", "error")
            return render_template('register.html', all_skills=all_skills())
        if len(pw) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template('register.html', all_skills=all_skills())

        resume_file = None
        resume = request.files.get('resume')
        if resume and resume.filename:
            resume_file = f"{u}_resume.pdf"
            resume.save(os.path.join(UPLOAD_DIR, resume_file))

        ok, err = db_create_user(u, pw, n, em, sk, go, ni, rm, resume_file)
        if not ok:
            flash(err, "error")
            return render_template('register.html', all_skills=all_skills())

        session.clear()
        session['username'] = u
        session['role']     = 'user'
        session['notifications'] = []
        db_log(u, "Registered")
        notif(f"🎉 Welcome {n}! Your account is ready.", "Welcome")
        send_email(em, "Welcome to Skill Navigator!",
                   f"Hi {n},\n\nYour account is ready.\n\nSkill Navigator Team")

        flash(f"Welcome, {n}! Here are your matched jobs.", "success")
        jobs = match_jobs(sk) if not rm else []
        return render_template('dashboard.html', name=n, jobs=jobs,
                               user_skills=sk, gaps=skill_gap(sk),
                               applied_count=0, saved_count=0)
    return render_template('register.html', all_skills=all_skills())

@app.route('/user-login', methods=['POST'])
def user_login():
    u  = request.form.get('username', '').strip()
    pw = request.form.get('password', '')
    user = db_get_user(u)
    if user and user['password'] == hp(pw):
        session.clear()
        session['username'] = u
        session['role']     = 'user'
        session['notifications'] = []
        db_log(u, "Logged in")
        notif("🔐 Login successful", "Login")
        flash(f"Welcome back, {user['name']}!", "success")
        return render_template('dashboard.html',
                               name=user['name'],
                               jobs=match_jobs(user.get('skills', '')),
                               user_skills=user.get('skills', ''),
                               gaps=skill_gap(user.get('skills', '')),
                               applied_count=db_app_count(u),
                               saved_count=len(db_saved(u)))
    flash("Invalid username or password.", "error")
    return redirect(url_for('login_page'))

@app.route('/company-login', methods=['POST'])
def company_login():
    u  = request.form.get('username', '').strip()
    pw = request.form.get('password', '')
    if u in COMPANY_CREDS and COMPANY_CREDS[u] == hp(pw):
        session.clear()
        session['username'] = u
        session['role']     = 'company'
        session['notifications'] = []
        db_log(u, "Company admin logged in")
        notif("🔐 Admin session started", "Login")
        flash("Welcome back, Admin!", "success")
        return redirect(url_for('company_dashboard'))
    flash("Invalid company credentials.", "error")
    return redirect(url_for('login_page'))

@app.route('/dashboard')
@login_required
def dashboard():
    user = db_get_user(session['username'])
    if not user:
        session.clear()
        flash("Session expired. Please log in again.", "error")
        return redirect(url_for('login_page'))
    u = session['username']
    return render_template('dashboard.html',
                           name=user['name'],
                           jobs=match_jobs(user.get('skills', '')),
                           user_skills=user.get('skills', ''),
                           gaps=skill_gap(user.get('skills', '')),
                           applied_count=db_app_count(u),
                           saved_count=len(db_saved(u)))

@app.route('/company_dashboard')
@login_required
@company_required
def company_dashboard():
    jobs = load_jobs()
    return render_template('companydashboard.html',
                           jobs=jobs,
                           recent_activity_list=db_activity(session['username']),
                           total_apps=db_total_apps(),
                           total_users=db_user_count())

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = db_get_user(session['username'])
    if not user:
        session.clear()
        return redirect(url_for('login_page'))
    if request.method == 'POST':
        db_update_user(session['username'],
                       request.form.get('name', '').strip(),
                       request.form.get('skills', '').strip(),
                       request.form.get('goal', '').strip(),
                       request.form.get('niche', '').strip())
        db_log(session['username'], "Updated profile")
        notif("📝 Profile updated", "Profile")
        flash("Profile saved successfully!", "success")
        return redirect(url_for('dashboard'))
    u = session['username']
    return render_template('profile.html', user=user,
                           applications=db_my_apps(u),
                           saved_jobs=db_saved(u),
                           all_skills=all_skills())

@app.route('/notifications')
@login_required
def notifications():
    return render_template('notifications.html',
                           notifications=session.get('notifications', []))

@app.route('/clear-notifications', methods=['POST'])
@login_required
def clear_notifications():
    session['notifications'] = []
    return jsonify({'ok': True})

@app.route('/skill-gap')
@login_required
def skill_gap_page():
    user = db_get_user(session['username'])
    if not user:
        return redirect(url_for('login_page'))
    return render_template('skill_gap.html',
                           gaps=skill_gap(user.get('skills', '')),
                           user=user,
                           all_skills=all_skills())

@app.route('/my-applications')
@login_required
def my_applications():
    return render_template('my_applications.html',
                           applications=db_my_apps(session['username']))

@app.route('/apply-job', methods=['POST'])
@login_required
def apply_job():
    d    = request.get_json()
    u    = session['username']
    user = db_get_user(u)
    title   = d.get('title', '')
    company = d.get('company', '')
    resume  = os.path.join(UPLOAD_DIR, f"{u}_resume.pdf")
    send_email(
        d.get('email', ''),
        f"Application: {title} at {company}",
        f"Dear {company},\n\nI am applying for {title}.\n\n"
        f"Applicant: {user['name']}\nEmail: {user['email']}\n"
        f"Skills: {d.get('skills', '')}\n\nBest,\n{user['name']}",
        attach=resume if os.path.exists(resume) else None
    )
    db_log_apply(u, title, company, d.get('location', ''), d.get('package', ''))
    db_log(u, f"Applied for {title} at {company}")
    notif(f"📩 Applied for {title} at {company}", "Application")
    return jsonify({"message": "Application sent!",
                    "applied_count": db_app_count(u)})

@app.route('/save-job', methods=['POST'])
@login_required
def save_job():
    d = request.get_json()
    u = session['username']
    if d.get('action') == 'save':
        db_save(u, d.get('job_title', ''), d.get('company', ''))
        return jsonify({'status': 'saved'})
    db_unsave(u, d.get('job_title', ''), d.get('company', ''))
    return jsonify({'status': 'unsaved'})

@app.route('/post-job', methods=['GET', 'POST'])
@login_required
@company_required
def post_job_page():
    if request.method == 'POST':
        title   = (request.form.get('custom_title') or
                   request.form.get('job_title', '')).strip()
        company = request.form.get('company', '').strip()
        pkg     = request.form.get('package', '').strip()
        loc     = request.form.get('location', '').strip()
        email   = request.form.get('email', '').strip()
        skills  = request.form.get('skills_required', '').strip()

        if not all([title, company, pkg, loc, skills]):
            flash("All required fields must be filled.", "error")
            return render_template('post_job.html', all_skills=all_skills(),
                                   locations=LOCATIONS, packages=PACKAGES,
                                   job_titles=JOB_TITLES)

        # Append to JobList.xlsx
        jl = os.path.join(DATA_DIR, 'JobList.xlsx')
        df = pd.read_excel(jl) if os.path.exists(jl) else pd.DataFrame()
        new_id = int(df['Job id'].max() + 1) \
                 if len(df) and 'Job id' in df.columns else 1
        df = pd.concat([df, pd.DataFrame([{
            'Job id': new_id, 'Job Title': title,
            'Skills Required': skills, 'Company': company,
            'Package': pkg, 'Location': loc, 'Email': email
        }])], ignore_index=True)
        df.to_excel(jl, index=False)

        # Append to Jobskills.xlsx
        js = os.path.join(DATA_DIR, 'Jobskills.xlsx')
        js_df = (pd.read_excel(js) if os.path.exists(js) else pd.DataFrame())
        js_df = pd.concat([js_df, pd.DataFrame([{
            'Job Title': title, 'Skills Required': skills
        }])], ignore_index=True)
        js_df.to_excel(js, index=False)

        # Notify matching users
        req = {s.strip().lower() for s in skills.split(',') if s.strip()}
        with get_db() as db:
            users = db.execute(
                "SELECT name,email,skills FROM users").fetchall()
        for usr in users:
            u_sk = {s.strip().lower()
                    for s in str(usr['skills']).split(',') if s.strip()}
            if req and len(u_sk & req) >= len(req) / 2:
                send_email(
                    usr['email'],
                    f"New Job Match: {title} at {company}",
                    f"Hi {usr['name']},\n\nNew matching job:\n"
                    f"{title} at {company}\n{pkg} | {loc}\n"
                    f"Skills: {skills}\n\nLog in to apply!")

        db_log(session['username'], f"Posted: {title} at {company}")
        notif(f"📢 Job posted: {title}", "Job Posted")
        flash(f"Job '{title}' posted! Matching candidates notified.", "success")
        return redirect(url_for('company_dashboard'))

    return render_template('post_job.html', all_skills=all_skills(),
                           locations=LOCATIONS, packages=PACKAGES,
                           job_titles=JOB_TITLES)

@app.route('/edit_job/<int:job_id>', methods=['GET', 'POST'])
@login_required
@company_required
def edit_job(job_id):
    jl = os.path.join(DATA_DIR, 'JobList.xlsx')
    df = pd.read_excel(jl)
    mask = df['Job id'] == job_id
    if not mask.any():
        flash("Job not found.", "error")
        return redirect(url_for('company_dashboard'))
    if request.method == 'POST':
        df.loc[mask, 'Job Title']       = request.form.get('job_title', '')
        df.loc[mask, 'Company']         = request.form.get('company', '')
        df.loc[mask, 'Package']         = request.form.get('package', '')
        df.loc[mask, 'Location']        = request.form.get('location', '')
        df.loc[mask, 'Skills Required'] = request.form.get('skills_required', '')
        df.loc[mask, 'Email']           = request.form.get('email', '')
        df.to_excel(jl, index=False)
        db_log(session['username'], f"Edited job #{job_id}")
        notif(f"✏️ Job #{job_id} updated", "Job Updated")
        flash("Job updated successfully!", "success")
        return redirect(url_for('company_dashboard'))
    job = df[mask].iloc[0].to_dict()
    return render_template('edit_job.html', job=job, job_id=job_id,
                           all_skills=all_skills(),
                           locations=LOCATIONS, packages=PACKAGES)

@app.route('/delete_job/<int:job_id>', methods=['POST'])
@login_required
@company_required
def delete_job(job_id):
    jl = os.path.join(DATA_DIR, 'JobList.xlsx')
    df = pd.read_excel(jl)
    if not (df['Job id'] == job_id).any():
        flash("Job not found.", "error")
        return redirect(url_for('company_dashboard'))
    df = df[df['Job id'] != job_id]
    df.to_excel(jl, index=False)
    db_log(session['username'], f"Deleted job #{job_id}")
    notif(f"🗑️ Job #{job_id} deleted", "Deleted")
    flash("Job deleted.", "info")
    return redirect(url_for('company_dashboard'))

@app.route('/logout')
def logout():
    u = session.get('username', '')
    if u:
        db_log(u, "Logged out")
    session.clear()
    flash("You've been logged out.", "info")
    return redirect(url_for('home'))

@app.route('/api/jobs')
def api_jobs():
    jobs = load_jobs()
    q   = request.args.get('q', '').lower()
    loc = request.args.get('location', '').lower()
    co  = request.args.get('company', '').lower()
    if q:   jobs = [j for j in jobs if q in j.get('Job Title','').lower()
                    or q in j.get('Skills Required','').lower()]
    if loc: jobs = [j for j in jobs if j.get('Location','').lower() == loc]
    if co:  jobs = [j for j in jobs if j.get('Company','').lower() == co]
    return jsonify(jobs[:50])

@app.route('/api/stats')
def api_stats():
    try:
        return jsonify({'jobs': len(load_jobs()),
                        'users': db_user_count(),
                        'applications': db_total_apps()})
    except Exception:
        return jsonify({'jobs': 0, 'users': 0, 'applications': 0})

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html', error=str(e)), 500

# ═════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    init_db()
    print("\n" + "="*55)
    print("  🚀  Skill Navigator is running!")
    print(f"  📁  Project root : {HERE}")
    print(f"  📂  Templates    : {TEMPLATE_DIR}")
    print(f"  🗄️   Database     : {DB_PATH}")
    print("  🌐  Open         : http://localhost:5000")
    print("  🔑  Admin login  : admin / 1234")
    print("="*55 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5000)
