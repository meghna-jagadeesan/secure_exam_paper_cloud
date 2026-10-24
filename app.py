
import os
import io
import secrets
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, send_file, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from cryptography.fernet import Fernet, InvalidToken

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "exam_cloud.db")
KEY_PATH = os.path.join(APP_DIR, "secret.key")

app = Flask(__name__)
app.secret_key = os.environ.get(
    "FLASK_SECRET", "change-this-development-secret"
)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024


# ---------- ENCRYPTION ----------

def get_fernet():
    if not os.path.exists(KEY_PATH):
        with open(KEY_PATH, "wb") as f:
            f.write(Fernet.generate_key())

    with open(KEY_PATH, "rb") as f:
        return Fernet(f.read())


# ---------- DATABASE ----------

def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def log_action(username, action, details=""):
    con = connect()
    con.execute(
        """INSERT INTO audit_logs
        (username, action, details, created_at)
        VALUES (?, ?, ?, ?)""",
        (
            username,
            action,
            details[:250],
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    con.commit()
    con.close()


def init_db():
    con = connect()

    con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            otp_code TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            filename TEXT NOT NULL,
            encrypted_content BLOB NOT NULL,
            release_at TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL
        );
    """)

    users = [
        ("admin", "Admin@123", "admin", "123456"),
        ("examiner", "Exam@123", "examiner", "234567"),
        ("student", "Student@123", "student", "345678"),
    ]

    for username, password, role, otp in users:
        con.execute(
            """INSERT OR IGNORE INTO users
            (username, password_hash, role, otp_code)
            VALUES (?, ?, ?, ?)""",
            (
                username,
                generate_password_hash(password),
                role,
                otp,
            ),
        )

    con.commit()
    con.close()


# ---------- ACCESS CONTROL DECORATORS ----------

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)

    return wrapper


def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if session.get("role") not in roles:
                abort(403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator


# ---------- TEMPLATE HELPERS ----------

@app.template_filter("datetimeformat")
def datetimeformat(value):
    return datetime.fromisoformat(value)


@app.context_processor
def inject_now():
    return {"now": datetime.now()}


# ---------- HOME ----------

@app.route("/")
def home():
    if "username" in session:
        return redirect(url_for("dashboard"))
    return render_template("home.html")


# ---------- LOGIN ----------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        con = connect()
        user = con.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        con.close()

        if user and check_password_hash(
            user["password_hash"], password
        ):
            session["pending_user"] = username
            log_action(
                username,
                "PASSWORD_VERIFIED",
                "Waiting for OTP verification",
            )
            return redirect(url_for("verify_otp"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    username = session.get("pending_user")

    if not username:
        return redirect(url_for("login"))

    if request.method == "POST":
        otp = request.form.get("otp", "").strip()

        con = connect()
        user = con.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        con.close()

        if user and secrets.compare_digest(otp, user["otp_code"]):
            session.clear()
            session["username"] = user["username"]
            session["role"] = user["role"]

            log_action(username, "LOGIN_SUCCESS", "OTP verified")
            return redirect(url_for("dashboard"))

        log_action(username, "LOGIN_FAILED", "Invalid OTP")
        flash("Incorrect OTP. Please try again.", "error")

    return render_template("otp.html", username=username)


# ---------- LOGOUT ----------

@app.route("/logout")
@login_required
def logout():
    username = session["username"]
    log_action(username, "LOGOUT")
    session.clear()
    return redirect(url_for("home"))


# ---------- DASHBOARD ----------

@app.route("/dashboard")
@login_required
def dashboard():
    con = connect()

    papers = con.execute(
        """SELECT id, title, filename, release_at, created_by, created_at
        FROM papers ORDER BY id DESC"""
    ).fetchall()

    logs = []
    if session["role"] == "admin":
        logs = con.execute(
            """SELECT username, action, details, created_at
            FROM audit_logs ORDER BY id DESC LIMIT 8"""
        ).fetchall()

    con.close()

    return render_template(
        "dashboard.html",
        papers=papers,
        logs=logs,
    )


# ---------- UPLOAD QUESTION PAPER ----------

@app.route("/upload", methods=["GET", "POST"])
@login_required
@roles_required("admin", "examiner")
def upload():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        release_at = request.form.get("release_at", "").strip()
        uploaded = request.files.get("paper")

        if not title or not release_at or not uploaded or not uploaded.filename:
            flash("Complete all fields and choose a file.", "error")
            return redirect(url_for("upload"))

        try:
            release_dt = datetime.strptime(
                release_at, "%Y-%m-%dT%H:%M"
            )
        except ValueError:
            flash("Invalid release date and time.", "error")
            return redirect(url_for("upload"))

        content = uploaded.read()

        if not content:
            flash("The uploaded file is empty.", "error")
            return redirect(url_for("upload"))

        encrypted = get_fernet().encrypt(content)

        con = connect()
        con.execute(
            """INSERT INTO papers
            (title, filename, encrypted_content, release_at,
             created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (
                title,
                os.path.basename(uploaded.filename),
                encrypted,
                release_dt.isoformat(timespec="minutes"),
                session["username"],
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        paper_id = con.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]
        con.commit()
        con.close()

        log_action(
            session["username"],
            "PAPER_ENCRYPTED_UPLOADED",
            f"Paper ID {paper_id}: {title}",
        )

        flash(
            "Question paper encrypted and uploaded successfully.",
            "success",
        )
        return redirect(url_for("dashboard"))

    default_time = (
        datetime.now() + timedelta(minutes=2)
    ).strftime("%Y-%m-%dT%H:%M")

    return render_template(
        "upload.html",
        default_time=default_time,
    )


# ---------- VIEW QUESTION PAPER ----------

@app.route("/paper/<int:paper_id>")
@login_required
def view_paper(paper_id):
    con = connect()
    paper = con.execute(
        "SELECT * FROM papers WHERE id = ?",
        (paper_id,),
    ).fetchone()
    con.close()

    if not paper:
        abort(404)

    release_dt = datetime.fromisoformat(paper["release_at"])

    if datetime.now() < release_dt:
        log_action(
            session["username"],
            "RELEASE_BLOCKED",
            f"Paper ID {paper_id} is not yet released",
        )
        return render_template(
            "locked.html",
            paper=paper,
            release_dt=release_dt,
        ), 403

    try:
        content = get_fernet().decrypt(
            paper["encrypted_content"]
        )
    except InvalidToken:
        log_action(
            session["username"],
            "DECRYPTION_FAILED",
            f"Paper ID {paper_id}",
        )
        abort(500)

    log_action(
        session["username"],
        "PAPER_VIEWED",
        f"Paper ID {paper_id}",
    )

    try:
        text_content = content.decode("utf-8")
        return render_template(
            "viewer.html",
            paper=paper,
            content=text_content,
        )
    except UnicodeDecodeError:
        return send_file(
            io.BytesIO(content),
            mimetype="application/octet-stream",
            as_attachment=False,
            download_name=paper["filename"],
        )


# ---------- AUDIT LOGS ----------

@app.route("/logs")
@login_required
@roles_required("admin")
def logs():
    con = connect()
    rows = con.execute(
        "SELECT * FROM audit_logs ORDER BY id DESC"
    ).fetchall()
    con.close()

    return render_template("logs.html", logs=rows)


# ---------- HEALTH CHECK ----------

@app.route("/health")
def health():
    return {
        "status": "ok",
        "service": "Secure Exam Paper Cloud",
    }


# ---------- ERROR HANDLERS ----------

@app.errorhandler(403)
def forbidden(error):
    return render_template(
        "error.html",
        code=403,
        message="Access denied. You do not have permission.",
    ), 403


@app.errorhandler(404)
def not_found(error):
    return render_template(
        "error.html",
        code=404,
        message="The requested page or paper was not found.",
    ), 404


# ---------- START APPLICATION ----------

if __name__ == "__main__":
    init_db()
    get_fernet()
    app.run(debug=True)