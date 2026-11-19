import os
import re
import hashlib
import secrets
import hmac
import sqlite3
from pathlib import Path
from nicegui import app, ui

try:
    import profile_settings
except Exception:
    profile_settings = None

# SQLite database path
DB_PATH = Path(__file__).with_name("nexora.db")

def get_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

# Ensure users table exists with all required columns
def init_db():
    try:
        with get_db() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    name TEXT,
                    full_name TEXT,
                    email TEXT UNIQUE,
                    phone TEXT,
                    role TEXT,
                    status TEXT,
                    password_hash TEXT,
                    password_salt TEXT
                )
            """)
            con.commit()
    except Exception as e:
        print("Database initialization error:", e)

init_db()


def hash_password(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        310000
    ).hex()


def register_user(username, name, email, phone, password):
    username = (username or "").strip()
    name = (name or "").strip() or "User"
    email = (email or "").strip().lower()
    phone = (phone or "").strip()
    password = password or ""

    if not username:
        return False, "Please enter a username."

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return False, "Please enter a valid email address."

    if len(password) < 8:
        return False, "Password must be at least 8 characters long."

    salt = secrets.token_hex(16)
    password_hash = hash_password(password, salt)

    try:
        with get_db() as con:
            con.execute("""
                INSERT INTO users (username, name, full_name, email, phone, role, status, password_hash, password_salt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (username, name, name, email, phone, "User", "Active", password_hash, salt))
            con.commit()
        return True, "Registration successful! Please log in."
    
    except sqlite3.IntegrityError as e:
        err_msg = str(e).lower()
        if "username" in err_msg:
            return False, "This username is already taken."
        elif "email" in err_msg:
            return False, "This email is already registered."
        return False, "Username or email already exists."
    except Exception as e:
        return False, f"Database error: {e}"


def authenticate_user(identifier, password):
    identifier = (identifier or "").strip().lower()

    try:
        with get_db() as con:
            cursor = con.cursor()
            # Check by email or username (case-insensitive lookup)
            cursor.execute("""
                SELECT * FROM users 
                WHERE LOWER(email) = ? OR LOWER(username) = ?
            """, (identifier, identifier))
            user = cursor.fetchone()

        if not user:
            return None

        entered_hash = hash_password(password or "", user["password_salt"] or "")

        if not hmac.compare_digest(entered_hash, user["password_hash"] or ""):
            return None

        display_name = user["full_name"] or user["name"] or "User"
        phone_val = ""
        try:
            phone_val = (user["phone"] or "").strip()
        except Exception:
            phone_val = ""

        return {
            "id": str(user["id"]),
            "username": user["username"] or "",
            "name": display_name,
            "email": user["email"] or "",
            "phone": phone_val,
            "role": user["role"] or "User",
            "status": user["status"] or "Active",
        }

    except Exception as e:
        print("Auth error:", e)
        return None


def is_authenticated():
    return bool(app.storage.user.get("user_id"))


def require_login():
    if not is_authenticated():
        ui.navigate.to("/login")
        return False
    return True


def current_user():
    uid = app.storage.user.get("user_id")
    role = app.storage.user.get("user_role", "User")
    email = app.storage.user.get("user_email", "")
    phone = app.storage.user.get("user_phone", "")

    if uid or email:
        try:
            with get_db() as con:
                if uid:
                    row = con.execute("SELECT role, status, phone FROM users WHERE id = ?", (uid,)).fetchone()
                else:
                    row = con.execute("SELECT role, status, phone FROM users WHERE LOWER(email) = ?", (email.lower(),)).fetchone()
                if row:
                    role = row["role"] or role
                    phone = (row["phone"] or phone or "").strip()
                    app.storage.user["user_role"] = role
                    app.storage.user["user_phone"] = phone
                    app.storage.user["user_status"] = row["status"] or app.storage.user.get("user_status", "Active")
        except Exception:
            pass

    user_data = {
        "id": uid,
        "username": app.storage.user.get("user_username", ""),
        "name": app.storage.user.get("user_name", ""),
        "email": email,
        "phone": phone,
        "role": role,
        "status": app.storage.user.get("user_status", "Active"),
    }
    if profile_settings is not None and uid:
        profile_settings.set_active_session_user(user_data, app.storage.user)
    return user_data


def logout():
    app.storage.user.clear()
    ui.navigate.to("/login")


@ui.page("/login")
def login_page():
    if is_authenticated():
        ui.navigate.to("/")
        return

    with ui.column().classes(
        "w-full min-h-screen items-center justify-center p-4"
    ).style("background:#080d1b"):

        with ui.card().classes("w-full max-w-md p-8").style(
            "background:#14213b;border:1px solid #334466;border-radius:20px"
        ):
            ui.label("◆ NEXORA").style(
                "font-size:30px;font-weight:900;letter-spacing:4px;color:white"
            )
            ui.label("BUSINESS MANAGEMENT").style(
                "color:#9db1d4;letter-spacing:2px"
            )
            ui.separator()

            ui.label("Welcome Back").style(
                "font-size:25px;font-weight:bold;color:white"
            )

            identifier = ui.input("Email or Username").props(
                "outlined"
            ).classes("w-full")

            password = ui.input(
                "Password",
                password=True,
                password_toggle_button=True
            ).props("outlined").classes("w-full")

            def do_login():
                user = authenticate_user(identifier.value, password.value)

                if not user:
                    ui.notify(
                        "Incorrect email/username or password.",
                        type="negative"
                    )
                    return

                app.storage.user["user_id"] = user["id"]
                app.storage.user["user_username"] = user["username"]
                app.storage.user["user_name"] = user["name"]
                app.storage.user["user_email"] = user["email"]
                app.storage.user["user_phone"] = user.get("phone", "")
                app.storage.user["user_role"] = user["role"]
                app.storage.user["user_status"] = user["status"]
                if profile_settings is not None:
                    profile_settings.set_active_session_user(user, app.storage.user)

                ui.notify("Login successful!", type="positive")
                ui.navigate.to("/")

            ui.button("LOGIN", on_click=do_login).props(
                "color=primary"
            ).classes("w-full mt-4")

            with ui.row().classes("w-full justify-center items-center mt-2"):
                ui.label("New to NEXORA?").style("color:#aab8d0")
                ui.button(
                    "Create Account",
                    on_click=lambda: ui.navigate.to("/register")
                ).props("flat color=primary")


@ui.page("/register")
def register_page():
    if is_authenticated():
        ui.navigate.to("/")
        return

    with ui.column().classes(
        "w-full min-h-screen items-center justify-center p-4"
    ).style("background:#080d1b"):

        with ui.card().classes("w-full max-w-md p-8").style(
            "background:#14213b;border:1px solid #334466;border-radius:20px"
        ):
            ui.label("◆ NEXORA").style(
                "font-size:28px;font-weight:900;letter-spacing:4px;color:white"
            )
            ui.label("CREATE YOUR ACCOUNT").style(
                "color:#9db1d4;letter-spacing:2px"
            )
            ui.separator()

            username = ui.input("Username").props("outlined").classes("w-full")
            name = ui.input("Full Name").props("outlined").classes("w-full")
            email = ui.input("Email Address").props(
                "outlined type=email"
            ).classes("w-full")
            phone = ui.input("Mobile Number").props(
                "outlined"
            ).classes("w-full")
            password = ui.input(
                "Password (minimum 8 characters)",
                password=True,
                password_toggle_button=True
            ).props("outlined").classes("w-full")
            confirm = ui.input(
                "Confirm Password",
                password=True,
                password_toggle_button=True
            ).props("outlined").classes("w-full")

            def do_register():
                if (password.value or "") != (confirm.value or ""):
                    ui.notify("Passwords do not match.", type="warning")
                    return

                success, message = register_user(
                    username.value,
                    name.value,
                    email.value,
                    phone.value,
                    password.value
                )

                if not success:
                    ui.notify(message, type="negative")
                    return

                ui.notify(message, type="positive")
                ui.navigate.to("/login")

            ui.button(
                "CREATE ACCOUNT",
                on_click=do_register
            ).props("color=primary").classes("w-full mt-4")

            ui.button(
                "Back to Login",
                on_click=lambda: ui.navigate.to("/login")
            ).props("flat color=primary").classes("w-full mt-2")
