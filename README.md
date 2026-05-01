# 🚀 Skill Navigator — AI-Powered Job Matching System

## Quick Start (30 seconds)

```bash
# 1. Install dependencies
pip install flask pandas openpyxl python-dotenv

# 2. Run
python app.py

# 3. Open
http://localhost:5000
```

---

## Login Credentials

| Role | Username | Password |
|------|----------|----------|
| Company Admin | `admin` | `1234` |
| Job Seeker | Register at `/register` | Your choice |

---

## Email Notifications (Optional)

Create a `.env` file in the project root:
```
SECRET_KEY=any_random_string_here
EMAIL_USER=your_gmail@gmail.com
EMAIL_PASS=your_gmail_app_password
```
> Get a Gmail App Password at: myaccount.google.com → Security → 2-Step → App Passwords

The app runs perfectly without this — email calls are silently skipped.

---

## Project Structure

```
skill_navigator/
├── app.py                    ← Flask app (all routes + DB logic)
├── requirements.txt
├── .env.example              ← Copy to .env for email support
├── students.db               ← SQLite database (auto-created on first run)
├── backend/
│   ├── __init__.py
│   └── utils.py              ← Email utility
├── Data/
│   ├── JobList.xlsx          ← 202 job listings
│   ├── Jobskills.xlsx        ← Job → skills mapping (used for AI matching)
│   └── jobList.xml           ← Additional XML job source
├── uploads/                  ← User resumes (auto-created)
├── static/
│   └── images/               ← Company logos (optional)
└── templates/
    ├── base.html             ← Shared layout, nav, notification bell
    ├── home.html             ← Landing page with live stats
    ├── login.html            ← Tabbed: Job Seeker / Company
    ├── register.html         ← Registration + drag-drop resume
    ├── dashboard.html        ← Matched jobs, filters, apply modal
    ├── companydashboard.html ← Manage listings, activity log
    ├── profile.html          ← Edit skills, career goal, progress bar
    ├── post_job.html         ← Post new job with skill palette picker
    ├── edit_job.html         ← Edit existing job listing
    ├── skill_gap.html        ← Skill gap bar chart + learning links
    ├── my_applications.html  ← Track all applied jobs
    ├── notifications.html    ← Searchable notification center
    ├── 404.html              ← Custom not-found page
    └── 500.html              ← Custom error page
```

---

## Features

### Job Seeker
- ✅ Register with resume upload (drag & drop)
- ✅ Live skill tag preview as you type
- ✅ AI-powered job matching (≥50% skill overlap)
- ✅ Match % ring chart on every job card
- ✅ Missing skills shown per job card
- ✅ Filter by location, company, salary range
- ✅ Sort by best match / title / company
- ✅ One-click apply (resume auto-attached to email)
- ✅ Save / bookmark jobs
- ✅ Track all applications with dates
- ✅ Skill Gap Analysis page — bar chart + learning links
- ✅ Full 50-skill checklist (green = have it)
- ✅ Profile completeness progress bar
- ✅ In-app notification bell + drawer
- ✅ Real-time applied count (no page reload)

### Company Admin
- ✅ Secure login (password hashed)
- ✅ View all job listings with search + filters
- ✅ Post new job — writes to JobList.xlsx + auto-notifies matched users
- ✅ Edit any existing job listing
- ✅ Delete job listings
- ✅ Activity log (stored in SQLite with timestamps)
- ✅ Total applications counter
- ✅ Total registered users counter

### System
- ✅ SQLite database (users, applications, saved_jobs, activity_log)
- ✅ SHA-256 password hashing
- ✅ `@login_required` and `@company_required` decorators on all routes
- ✅ Custom 404 and 500 error pages
- ✅ `/api/jobs` and `/api/stats` JSON endpoints
- ✅ XML jobs merged with Excel data automatically
- ✅ App runs fine without email credentials configured
