from flask import Flask, render_template_string, request, redirect, url_for, session, flash
import sqlite3
import time 
from datetime import datetime, timedelta
import secrets
import hashlib
import os
from functools import wraps
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

government_code = {
    '01': 'Cairo', '02': 'Alexandria',
    '03': 'Port Said', '04': 'Suez',
    '11': 'Damietta', '12': 'Dakahlia',
    '13': 'Ash Sharqia', '14': 'Kaliobeya',
    '15': 'Kafr El-Sheikh', '16': 'Gharbia',
    '17': 'Menoufia', '18': 'Beheira',
    '19': 'Ismailia', '21': 'Giza', 
    '22': 'Beni Suef', '23': 'Fayoum',
    '24': 'Minya', '25': 'Assiut',
    '26': 'Sohag', '27': 'Qena',
    '28': 'Aswan', '29': 'Luxor',
    '31': 'Red Sea', '32': 'New Valley',
    '33': 'Matrouh', '34': 'North Sinai',
    '35': 'South Sinai', '88': 'Foreign'
}

class EgyptNationalID:
    def __init__(self,national_id):
        self.national_id = national_id
        self.birth_date  = None
        self.government  = None
        self.gender      = None
        self.age    = None
        self.valid       = self.validiate_national_id()
    
    def validiate_national_id(self):
        if len(self.national_id) !=14 or not self.national_id.isdigit():
            return False
        
        year=self.national_id[0]
        year_number=self.national_id[1:3]
        month = self.national_id[3:5]
        day = self.national_id[5:7]
        government_id = self.national_id[7:9]
        rest_of_id = self.national_id[9:13]
            
        if(year=="2"):
            full_year = "19" + year_number
        elif(year=="3"):
            full_year = "20" + year_number
        else:
            return False    
        
        if(int(rest_of_id) % 2==1):
            self.gender = "male" 
        else:
            self.gender =  "female"
        
        try:
            self.birth_date = datetime.strptime(f"{full_year}{month}{day}", "%Y%m%d")
            self.birth_date_str = self.birth_date.strftime("%Y-%m-%d")
        except ValueError:
            return False
        
        # government_code should be defined somewhere
        self.government = government_code.get(government_id, 'Unknown')
        
        # Calculate age
        today = datetime.now().date()
        birth = self.birth_date.date()
        self.age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
        
        return True        

class EmailConfig:
    SENDER_EMAIL = os.getenv("EMAIL_ADDRESS", "your_email@gmail.com")
    SENDER_PASSWORD = os.getenv("EMAIL_PASSWORD", "your_app_password")
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587

class EmailService:
    @staticmethod
    def send_verification_code(to_email, code, name):
        try:
            message = MIMEMultipart('alternative')
            message['From'] = EmailConfig.SENDER_EMAIL
            message['To'] = to_email
            message['Subject'] = f"Verification Code - {name}"
            html_body = f"""
            <html><body style="font-family: Arial; text-align: center; background: #f4f4f4; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px; border-radius: 20px;">
            <div style="background: white; max-width: 500px; margin: auto; padding: 40px; border-radius: 15px;">
            <h1 style="color: #667eea;">Hello {name}!</h1>
            <p style="color: #666; font-size: 16px;">Thank you for registering</p>
            <hr style="border: none; border-top: 2px solid #f0f0f0; margin: 20px 0;">
            <p style="color: #666; font-size: 18px;">Use this code to verify your account:</p>
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 10px; margin: 20px 0;">
            <p style="color: white; font-size: 48px; font-weight: bold; letter-spacing: 8px; margin: 0;">{code}</p>
            </div>
            <div style="background: #fff3cd; border: 2px solid #ffc107; border-radius: 8px; padding: 12px; margin: 20px 0;">
            <p style="color: #856404; font-size: 14px; margin: 0;">Code valid for 15 minutes</p>
            </div></div></div></body></html>
            """
            message.attach(MIMEText(html_body, 'html'))
            with smtplib.SMTP(EmailConfig.SMTP_SERVER, EmailConfig.SMTP_PORT) as server:
                server.starttls()
                server.login(EmailConfig.SENDER_EMAIL, EmailConfig.SENDER_PASSWORD)
                server.send_message(message)
            return True
        except Exception as e:
            print(f"Email error: {e}")
            return False

class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect('fuckn_complete_system.db',
                                     check_same_thread=False,
                                     timeout=10)
        self.conn.execute('PRAGMA journal_mode=WAL;')
        self.create_tables()
    
    def create_tables(self):
        c = self.conn.cursor()
        #pending user
        c.execute("""CREATE TABLE IF NOT EXISTS pending_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            national_id TEXT UNIQUE NOT NULL CHECK(length(national_id) = 14),
            birth_date TEXT,
            government TEXT,
            gender TEXT,
            age    INTEGER,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            code_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            attempts INTEGER DEFAULT 0)""")
        #main user
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            national_id TEXT UNIQUE NOT NULL CHECK(length(national_id) = 14),
            birth_date TEXT,
            government TEXT,
            gender TEXT,
            age    INTEGER,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            verified BOOLEAN DEFAULT 1,
            created_at TEXT NOT NULL, last_login TEXT)""")
        #session 
        c.execute("""CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_token TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id))""")
        self.conn.commit()

db = DatabaseManager()

def get_db():
    return db.conn

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

CSS = """<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; justify-content: center; align-items: center; padding: 20px; }
.container { background: white; border-radius: 20px; box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3); padding: 40px; max-width: 500px; width: 100%; animation: slideIn 0.5s ease; }
@keyframes slideIn { from { opacity: 0; transform: translateY(-20px); } to { opacity: 1; transform: translateY(0); } }
.dashboard-container { max-width: 900px; }
h1 { color: #667eea; margin-bottom: 10px; text-align: center; font-size: 28px; }
h2 { color: #667eea; margin-bottom: 30px; text-align: center; font-size: 24px; }
.form-group { margin-bottom: 20px; }
label { display: block; color: #333; font-weight: 600; margin-bottom: 8px; font-size: 14px; }
input[type="text"], input[type="email"], input[type="password"] { width: 100%; padding: 12px 15px; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 16px; transition: border-color 0.3s; }
input:focus { outline: none; border-color: #667eea; }
.btn { width: 100%; padding: 14px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 8px; font-size: 18px; font-weight: bold; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; margin-top: 10px; }
.btn:hover { transform: translateY(-2px); box-shadow: 0 10px 25px rgba(102, 126, 234, 0.4); }
.btn-secondary { background: linear-gradient(135deg, #6c757d 0%, #495057 100%); }
.btn-secondary:hover { box-shadow: 0 10px 25px rgba(108, 117, 125, 0.4); }
.links { text-align: center; margin-top: 20px; color: #666; font-size: 14px; }
.links a { color: #667eea; text-decoration: none; font-weight: 600; }
.links a:hover { text-decoration: underline; }
.alert { padding: 12px 20px; border-radius: 8px; margin-bottom: 20px; font-weight: 500; animation: fadeIn 0.3s ease; }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
.alert-success { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
.alert-error { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
.alert-warning { background-color: #fff3cd; color: #856404; border: 1px solid #ffc107; }
.user-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px; border-radius: 15px; margin-bottom: 30px; text-align: center; box-shadow: 0 10px 30px rgba(102, 126, 234, 0.4); }
.user-card h3 { font-size: 36px; margin-bottom: 10px; font-weight: bold; }
.user-card .email { font-size: 18px; opacity: 0.9; }
.info-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
.info-item { background: #f8f9fa; padding: 25px; border-radius: 12px; border-left: 5px solid #667eea; transition: transform 0.2s, box-shadow 0.2s; }
.info-item:hover { transform: translateY(-5px); box-shadow: 0 5px 20px rgba(0, 0, 0, 0.1); }
.info-label { color: #666; font-size: 12px; font-weight: 600; text-transform: uppercase; margin-bottom: 10px; letter-spacing: 1px; }
.info-value { color: #333; font-size: 20px; font-weight: bold; }
.verify-code { background: #fff3cd; border: 2px solid #ffc107; padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 25px; }
.verify-code p { color: #856404; font-weight: 600; margin: 5px 0; }
.verify-code strong { color: #664d03; }
input[type="text"].code-input { text-align: center; font-size: 32px; letter-spacing: 12px; font-weight: bold; font-family: 'Courier New', monospace; }
</style>"""

LOGIN_TEMPLATE = CSS + """
<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Login</title></head><body>
<div class="container"><h1>🇪🇬 Egyptian Authentication</h1><h2>🔐 Login</h2>
{% with messages = get_flashed_messages(with_categories=true) %}{% if messages %}{% for category, message in messages %}<div class="alert alert-{{ category }}">{{ message }}</div>{% endfor %}{% endif %}{% endwith %}
<form method="POST" action="{{ url_for('login') }}">
<div class="form-group"><label for="email">📧 Email Address</label><input type="email" id="email" name="email" required placeholder="your.email@example.com"></div>
<div class="form-group"><label for="password">🔒 Password</label><input type="password" id="password" name="password" required placeholder="Enter your password"></div>
<button type="submit" class="btn">🔓 Login to Dashboard</button></form>
<div class="links">Don't have an account? <a href="{{ url_for('register') }}">Register here</a></div></div></body></html>
"""

REGISTER_TEMPLATE = CSS + """
<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Register</title></head><body>
<div class="container"><h1>🇪🇬 Egyptian Authentication</h1><h2>📝 Register New Account</h2>
{% with messages = get_flashed_messages(with_categories=true) %}{% if messages %}{% for category, message in messages %}<div class="alert alert-{{ category }}">{{ message }}</div>{% endfor %}{% endif %}{% endwith %}
<form method="POST" action="{{ url_for('register') }}" id="registerForm">
<div class="form-group"><label for="national_id">🆔 National ID (14 digits)</label><input type="text" id="national_id" name="national_id" pattern="[0-9]{14}" maxlength="14" required placeholder="29901011234567"><small style="color: #666; font-size: 12px;">Example: 29901011234567</small></div>
<div class="form-group"><label for="first_name">👤 First Name</label><input type="text" id="first_name" name="first_name" required placeholder="Ahmed"></div>
<div class="form-group"><label for="last_name">👤 Last Name</label><input type="text" id="last_name" name="last_name" required placeholder="Mohamed"></div>
<div class="form-group"><label for="email">📧 Email Address</label><input type="email" id="email" name="email" required placeholder="your.email@example.com"></div>
<div class="form-group"><label for="password">🔒 Password</label><input type="password" id="password" name="password" required placeholder="Create a strong password"></div>
<button type="submit" class="btn" id="submitBtn">📧 Send Verification Code</button></form>
<div class="links">Already have an account? <a href="{{ url_for('login') }}">Login here</a></div></div>
<script>
// Prevent form resubmission on page reload
if (window.history.replaceState) {
    window.history.replaceState(null, null, window.location.href);
}

// Add loading state to button
document.getElementById('registerForm').addEventListener('submit', function() {
    const btn = document.getElementById('submitBtn');
    btn.disabled = true;
    btn.textContent = '⏳ Sending...';
});
</script>
</body></html>
"""
VERIFY_TEMPLATE = CSS + """
<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Verify</title></head><body>
<div class="container"><h1>🇪🇬 Egyptian Authentication</h1><h2>✅ Verify Your Account</h2>
<div class="verify-code"><p>📧 Check your email: <strong>{{ email }}</strong></p><p>⏰ Code valid for <strong>15 minutes</strong></p><p>🔢 Maximum <strong>3 attempts</strong></p></div>
{% with messages = get_flashed_messages(with_categories=true) %}{% if messages %}{% for category, message in messages %}<div class="alert alert-{{ category }}">{{ message }}</div>{% endfor %}{% endif %}{% endwith %}
<form method="POST" action="{{ url_for('verify') }}">
<div class="form-group"><label for="code">🔢 Enter 6-Digit Verification Code</label><input type="text" id="code" name="code" class="code-input" pattern="[0-9]{6}" maxlength="6" required placeholder="123456" autocomplete="off"></div>
<button type="submit" class="btn">✅ Verify & Access Dashboard</button></form>
<div class="links">Wrong email? <a href="{{ url_for('register') }}">Register again</a></div></div>
<script>document.getElementById('code').focus();</script></body></html>
"""

DASHBOARD_TEMPLATE = CSS + """
<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Dashboard</title></head><body>
<div class="container dashboard-container"><h1>🇪🇬 User Dashboard</h1>
{% with messages = get_flashed_messages(with_categories=true) %}{% if messages %}{% for category, message in messages %}<div class="alert alert-{{ category }}">{{ message }}</div>{% endfor %}{% endif %}{% endwith %}
<div class="user-card"><h3>👤 {{ user.first_name }} {{ user.last_name }}</h3><p class="email">📧 {{ user.email }}</p></div>
<div class="info-grid">
<div class="info-item"><div class="info-label">🆔 National ID</div><div class="info-value">{{ user.national_id }}</div></div>
<div class="info-item"><div class="info-label">🎂 Date of Birth</div><div class="info-value">{{ user.birth_date }}</div></div>
<div class="info-item"><div class="info-label">📍 Government</div><div class="info-value">{{ user.government }}</div></div>
<div class="info-item"><div class="info-label">⚧️ Gender</div><div class="info-value">{{ user.gender }}</div></div>
<div class="info-item"><div class="info-label"> age</div><div class="info-value">{{ user.age }}</div></div>
<div class="info-item"><div class="info-label">📅 Member Since</div><div class="info-value">{{ user.created_at[:10] }}</div></div>
<div class="info-item"><div class="info-label">🕐 Last Login</div><div class="info-value">{{ user.last_login[:10] if user.last_login else 'First Login' }}</div></div>
</div>
<a href="{{ url_for('logout') }}" style="text-decoration: none;"><button class="btn btn-secondary">🚪 Logout</button></a>
</div></body></html>
"""

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        national_id = request.form.get('national_id', '').strip()
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        if not all([national_id, first_name, last_name, email, password]):
            flash('All fields are required', 'error')
            return redirect(url_for('register'))
        egypt_id = EgyptNationalID(national_id)
        if not egypt_id.valid:
            flash('Invalid Egyptian National ID', 'error')
            return redirect(url_for('register'))
        conn = get_db()
        c = conn.execute("SELECT email FROM users WHERE email = ?", (email,))
        if c.fetchone():
            flash('Email already registered. Please login.', 'error')
            return redirect(url_for('login'))
        code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        created_at = datetime.now().isoformat()
        expires_at = (datetime.now() + timedelta(minutes=15)).isoformat()
        try:
            conn.execute('DELETE FROM pending_users WHERE email = ?', (email,))
            conn.execute('''INSERT INTO pending_users (national_id, birth_date, government, gender, age, first_name, last_name,  email, password_hash, code_hash, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (national_id, egypt_id.birth_date_str, egypt_id.government, egypt_id.gender, egypt_id.age,  first_name, last_name, email, password_hash, code_hash, created_at, expires_at))
            conn.commit()
            if EmailService.send_verification_code(email, code, first_name):
                session['pending_email'] = email
                flash(f'Verification code sent to {email}! Check your inbox.', 'success')
                return redirect(url_for('verify'))
            else:
                flash('Failed to send verification email.', 'error')
                return redirect(url_for('register'))
        except Exception as e:
            flash(f'Registration failed: {str(e)}', 'error')
            return redirect(url_for('register'))
    return render_template_string(REGISTER_TEMPLATE)

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if 'pending_email' not in session:
        flash('Please register first', 'warning')
        return redirect(url_for('register'))
    if request.method == 'POST':
        email = session.get('pending_email')
        code = request.form.get('code', '').strip()
        if not code:
            flash('Please enter verification code', 'error')
            return redirect(url_for('verify'))
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        conn = get_db()
        c = conn.execute("""SELECT national_id, birth_date, government, gender, age, first_name, last_name, password_hash, expires_at, attempts FROM pending_users WHERE email = ? AND code_hash = ?""", (email, code_hash))
        result = c.fetchone()
        if not result:
            conn.execute('UPDATE pending_users SET attempts = attempts + 1 WHERE email = ?', (email,))
            conn.commit()
            c = conn.execute('SELECT attempts FROM pending_users WHERE email = ?', (email,))
            attempts_result = c.fetchone()
            if attempts_result and attempts_result[0] >= 3:
                conn.execute('DELETE FROM pending_users WHERE email = ?', (email,))
                conn.commit()
                session.pop('pending_email', None)
                flash('Maximum attempts exceeded. Please register again.', 'error')
                return redirect(url_for('register'))
            remaining = 3 - (attempts_result[0] if attempts_result else 0)
            flash(f'Wrong code! Attempts remaining: {remaining}', 'error')
            return redirect(url_for('verify'))
        national_id, birth_date, government, gender, age, first_name, last_name, password_hash, expires_at, attempts = result
        if datetime.now() > datetime.fromisoformat(expires_at):
            conn.execute('DELETE FROM pending_users WHERE email = ?', (email,))
            conn.commit()
            session.pop('pending_email', None)
            flash('Verification code expired. Please register again.', 'error')
            return redirect(url_for('register'))
        try:
            created_at = datetime.now().isoformat()
            c = conn.execute('''INSERT INTO users (national_id, birth_date, government, gender, age, email, first_name, last_name, password_hash, created_at) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                             (national_id, birth_date, government, gender, age, email, first_name, last_name, password_hash, created_at))
            user_id = c.lastrowid
            conn.commit()
            conn.execute('DELETE FROM pending_users WHERE email = ?', (email,))
            conn.commit()
            session.pop('pending_email', None)
            session['user_id'] = user_id
            session['email'] = email
            session['first_name'] = first_name
            session['last_name'] = last_name
            session.permanent = True
            flash(f'Account verified successfully! Welcome {first_name}!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(f'Verification failed: {str(e)}', 'error')
            return redirect(url_for('verify'))
    return render_template_string(VERIFY_TEMPLATE, email=session.get('pending_email'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        if not email or not password:
            flash('Email and password are required', 'error')
            return redirect(url_for('login'))
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        conn = get_db()
        c = conn.execute("""SELECT id, first_name, last_name, national_id, birth_date, government,  gender, age FROM users WHERE email = ? AND password_hash = ?""", (email, password_hash))
        result = c.fetchone()
        if result:
            user_id, first_name, last_name, national_id, birth_date, government, gender, age = result
            session['user_id'] = user_id
            session['email'] = email
            session['first_name'] = first_name
            session['last_name'] = last_name
            session['national_id'] = national_id
            session['birth_date'] = birth_date
            session['government'] = government
            session['gender'] = gender
            session['age'] = age
            session.permanent = True
            last_login = datetime.now().isoformat()
            conn.execute('UPDATE users SET last_login = ? WHERE id = ?', (last_login, user_id))
            conn.commit()
            flash(f'Welcome back, {first_name}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'error')
            return redirect(url_for('login'))
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    c = conn.execute("""SELECT first_name, last_name, email, national_id, birth_date, government, gender, age, created_at, last_login FROM users WHERE id = ?""", (session['user_id'],))
    user = c.fetchone()
    if user:
        user_data = {
            'first_name': user[0], 
            'last_name': user[1], 'email': user[2], 'national_id': user[3], 'birth_date': user[4], 'government': user[5], 'gender': user[6], 'age': user[7], 'created_at': user[8], 'last_login': user[9]}
        return render_template_string(DASHBOARD_TEMPLATE, user=user_data)
    else:
        flash('User not found', 'error')
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    name = session.get('first_name', 'User')
    session.clear()
    flash(f'Goodbye {name}! Logged out successfully.', 'success')
    return redirect(url_for('login'))

# Function to run Flask in a separate thread for Jupyter
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)






