import sqlite3
import re
import hashlib
import secrets
import hmac
from pathlib import Path

from nicegui import app, ui

DB = Path(__file__).with_name("nexora.db")


def connect():
    con = sqlite3.connect(DB, timeout=15)
    con.row_factory = sqlite3.Row
    return con


def initialize_auth_database():
    with connect() as con:
        # Drop old table to clear out any conflicting constraints completely
        con.execute("DROP TABLE IF EXISTS users")
        con.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                full_name TEXT,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                phone TEXT,
                role TEXT DEFAULT 'User',
                status TEXT DEFAULT 'Active',
                password_hash TEXT DEFAULT '',
                password_salt TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


def hash_password(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        310000
    ).hex()


def register_user(name, email, phone, password):
    name = (name or "").strip() or "User"
    email = (email or "").strip().lower()
    phone = (phone or "").strip()
    password = password or ""

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return False, "कृपया एक वैध ईमेल दर्ज करें।"

    if len(password) < 8:
        return False, "पासवर्ड कम से कम 8 अक्षरों का होना चाहिए।"

    salt = secrets.token_hex(16)
    password_hash = hash_password(password, salt)

    try:
        with connect() as con:
            con.execute("""
                INSERT INTO users
                (name, full_name, email, phone, role, status, password_hash, password_salt)
                VALUES (?, ?, ?, ?, 'User', 'Active', ?, ?)
            """, (name, name, email, phone, password_hash, salt))
        return True, "पंजीकरण सफल रहा।"

    except sqlite3.IntegrityError:
        return False, "यह ईमेल पहले से रजिस्टर्ड है।"

    except sqlite3.Error as e:
        return False, f"डेटाबेस एरर: {e}"


def authenticate_user(email, password):
    email = (email or "").strip().lower()

    try:
        with connect() as con:
            user = con.execute("""
                SELECT id, name, full_name, email, role, status, password_hash, password_salt
                FROM users
                WHERE email = ? COLLATE NOCASE
            """, (email,)).fetchone()

        if not user:
            return None

        entered_hash = hash_password(password or "", user["password_salt"] or "")

        if not hmac.compare_digest(entered_hash, user["password_hash"] or ""):
            return None

        display_name = user["full_name"] or user["name"] or "User"
        return {
            "id": user["id"],
            "name": display_name,
            "email": user["email"],
            "role": user["role"] if "role" in user.keys() else "User",
            "status": user["status"] if "status" in user.keys() else "Active",
        }

    except sqlite3.Error:
        return None


def is_authenticated():
    return bool(app.storage.user.get("user_id"))


def require_login():
    if not is_authenticated():
        ui.navigate.to("/login")
        return False
    return True


def current_user():
    return {
        "id": app.storage.user.get("user_id"),
        "name": app.storage.user.get("user_name", ""),
        "email": app.storage.user.get("user_email", ""),
        "role": app.storage.user.get("user_role", "User"),
        "status": app.storage.user.get("user_status", "Active"),
    }


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

            email = ui.input("Email Address").props(
                "outlined type=email"
            ).classes("w-full")

            password = ui.input(
                "Password",
                password=True,
                password_toggle_button=True
            ).props("outlined").classes("w-full")

            def do_login():
                user = authenticate_user(email.value, password.value)

                if not user:
                    ui.notify(
                        "गलत ईमेल या पासवर्ड।",
                        type="negative"
                    )
                    return

                app.storage.user["user_id"] = user["id"]
                app.storage.user["user_name"] = user["name"]
                app.storage.user["user_email"] = user["email"]
                app.storage.user["user_role"] = user["role"]
                app.storage.user["user_status"] = user["status"]

                ui.notify("लॉगिन सफल!", type="positive")
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

            name = ui.input("Full Name").props("outlined").classes("w-full")
            email = ui.input("Email Address").props(
                "outlined type=email"
            ).classes("w-full")
            phone = ui.input("Mobile Number").props(
                "outlined"
            ).classes("w-full")
            password = ui.input(
                "Password (कम से कम 8 अक्षर)",
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
                    ui.notify("पासवर्ड मेल नहीं खा रहे हैं।", type="warning")
                    return

                success, message = register_user(
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


initialize_auth_database()
