# Grizzly Garage admin starter

A local Flask-backed starter with a public landing page, administrator login, inventory add/delete, and customer inquiries/status tracking.


## Local setup
1. Install Python 3.10+.
2. In this folder run: `python -m venv .venv`
3. Activate the virtual environment (Windows: `.venv\\Scripts\\activate`; macOS/Linux: `source .venv/bin/activate`).
4. Install: `pip install -r requirements.txt`
5. Create admin credentials: `python setup_admin.py` (password is stored as a Werkzeug password hash, not plain text).
6. Start: `python app.py`
7. Visit `http://127.0.0.1:5000/` for the public website and `http://127.0.0.1:5000/admin/login` for admin.

## Before production
- Deploy behind HTTPS; set `COOKIE_SECURE=1`.
- Use a hosting provider that supports Python/Flask, persistent storage, and environment variables. Set `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`, and `FLASK_SECRET_KEY` as host environment secrets (do not upload `.env`).
- Use a shared rate limiter and persistent database for multi-instance deployments.
- Configure the public inquiry form in the landing page to POST to `/api/inquiry` (currently the existing HTML form still uses its mailto behavior; backend endpoint is available but not wired into the page).
- Back up the SQLite database and test admin access after deployment.
- The provided public page contains placeholder email/phone and stock images; replace before launch.
