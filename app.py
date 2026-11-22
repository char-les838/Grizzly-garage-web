import os, sqlite3, secrets, time
from functools import wraps
from flask import Flask, request, session, redirect, url_for, render_template, flash, abort, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv
load_dotenv()


BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get('GRIZZLY_DB', os.path.join(BASE, 'grizzly.db'))
app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.environ.get('FLASK_SECRET_KEY') or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE','0') == '1', PERMANENT_SESSION_LIFETIME=3600)
if os.environ.get('TRUST_PROXY','0') == '1':
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)


def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with db() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, category TEXT NOT NULL,
            model_fitment TEXT DEFAULT '', price TEXT DEFAULT '', status TEXT DEFAULT 'Available',
            description TEXT DEFAULT '', image_url TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        con.execute('''CREATE TABLE IF NOT EXISTS inquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, customer_name TEXT NOT NULL, email TEXT NOT NULL,
            model_year TEXT NOT NULL, topic TEXT DEFAULT '', message TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP, status TEXT DEFAULT 'New'
        )''')

init_db()


@app.after_request
def headers(resp):
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    resp.headers['X-Frame-Options'] = 'DENY'
    resp.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    resp.headers['Content-Security-Policy'] = "default-src 'self' https: data:; img-src 'self' https: data:; style-src 'self' 'unsafe-inline' https:; script-src 'self' 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'"
    return resp


def csrf_token():
    if 'csrf' not in session: session['csrf'] = secrets.token_urlsafe(32)
    return session['csrf']
app.jinja_env.globals['csrf_token'] = csrf_token


def require_csrf():
    token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
    if not token or not secrets.compare_digest(token, session.get('csrf','')):
        abort(400, 'Invalid CSRF token')


def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
        return fn(*args, **kwargs)
    return wrapped


# Basic in-process login throttling; for multi-instance deployments use a shared rate limiter.ailed_logins = {}
@app.route('/admin/login', methods=['GET','POST'])
def admin_login():
    if session.get('admin_logged_in'): return redirect(url_for('dashboard'))
    if request.method == 'POST':
        require_csrf()
        ip = request.remote_addr or 'unknown'
        state = failed_logins.get(ip, {'count':0,'until':0})
        if state['until'] > time.time():
            flash('Too many failed attempts. Try again later.'); return render_template('login.html')
        username = os.environ.get('ADMIN_USERNAME','admin')
        password_hash = os.environ.get('ADMIN_PASSWORD_HASH','')
        ok = request.form.get('username','') == username and password_hash and check_password_hash(password_hash, request.form.get('password',''))
        if ok:
            failed_logins.pop(ip, None); session.clear(); session['admin_logged_in']=True; session['admin_username']=username; session['csrf']=secrets.token_urlsafe(32); session.permanent=True
            return redirect(url_for('dashboard'))
        state['count'] += 1
        if state['count'] >= 5: state['until'] = time.time() + 300; state['count']=0
        failed_logins[ip]=state
        flash('Invalid username or password.')
    return render_template('login.html')


@app.post('/admin/logout')
@admin_required
def admin_logout():
    require_csrf(); session.clear(); return redirect(url_for('admin_login'))


@app.route('/admin')
@admin_required
def dashboard():
    with db() as con:
        products=con.execute('SELECT * FROM products ORDER BY id DESC').fetchall()
        inquiries=con.execute('SELECT * FROM inquiries ORDER BY id DESC').fetchall()
    return render_template('dashboard.html', products=products, inquiries=inquiries)


@app.post('/admin/products/add')
@admin_required
def add_product():
    require_csrf()
    vals=[request.form.get(k,'').strip() for k in ('name','category','model_fitment','price','status','description','image_url')]
    if not vals[0] or not vals[1]: flash('Product name and category are required.')
    else:
        with db() as con: con.execute('INSERT INTO products(name,category,model_fitment,price,status,description,image_url) VALUES(?,?,?,?,?,?,?)', vals)
        flash('Product added.')
    return redirect(url_for('dashboard'))

@app.post('/admin/products/<int:pid>/delete')
@admin_required
def delete_product(pid):
    require_csrf()
    with db() as con: con.execute('DELETE FROM products WHERE id=?', (pid,))
    flash('Product removed.'); return redirect(url_for('dashboard'))

@app.post('/admin/inquiries/<int:iid>/status')
@admin_required
def inquiry_status(iid):
    require_csrf(); status=request.form.get('status','New')
    if status not in ('New','Contacted','Closed'): abort(400)
    with db() as con: con.execute('UPDATE inquiries SET status=? WHERE id=?',(status,iid))
    return redirect(url_for('dashboard'))

@app.post('/api/inquiry')
def public_inquiry():
    # Minimal spam guard: honeypot field must remain empty.
    if request.form.get('website','').strip(): return jsonify(ok=True), 200
    name=request.form.get('name','').strip()[:120]
    email=request.form.get('email','').strip()[:254]
    model=request.form.get('model_year','').strip()[:120]
    topic=request.form.get('topic','').strip()[:120]
    message=request.form.get('message','').strip()[:4000]
    if not name or not email or not model or '@' not in email: return jsonify(ok=False,error='Please fill in the required fields.'),400
    with db() as con: con.execute('INSERT INTO inquiries(customer_name,email,model_year,topic,message) VALUES(?,?,?,?,?)',(name,email,model,topic,message))
    return jsonify(ok=True), 201


@app.route('/')
def home(): return render_template('index.html')


@app.errorhandler(400)
def bad_request(e): return render_template('error.html', code=400, message='Your request could not be verified.'),400


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT','5000')), debug=False)
