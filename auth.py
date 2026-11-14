import os
import re
import hashlib
import secrets
import hmac
from pymongo import MongoClient
from nicegui import app, ui

# MongoDB Atlas connection (uses Environment Variable on Render; paste your URI below for local testing)
MONGO_URI = os.environ.get("MONGO_URI", "PASTE_YOUR_MONGODB_CONNECTION_STRING_HERE")

client = MongoClient(MONGO_URI)
db = client["nexora_db"]
users_collection = db["users"]

# Ensure unique indexes on username and email
try:
    users_collection.create_index("username", unique=True)
    users_collection.create_index("email", unique=True)
except Exception as e:
    print("Index notice:", e)


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

    # Check if username or email already exists
    existing_user = users_collection.find_one({"$or": [{"username": username}, {"email": email}]})
    if existing_user:
        if existing_user.get("username") == username:
            return False, "This username is already taken."
        return False, "This email is already registered."

    salt = secrets.token_hex(16)
    password_hash = hash_password(password, salt)

    try:
        users_collection.insert_one({
            "username": username,
            "name": name,
            "full_name": name,
            "email": email,
            "phone": phone,
            "role": "User",
            "status": "Active",
            "password_hash": password_hash,
            "password_salt": salt
        })
        return True, "Registration successful! Please log in."

    except Exception as e:
        return False, f"Database error: {e}"


def authenticate_user(identifier, password):
    identifier = (identifier or "").strip().lower()

    try:
        # Case-insensitive search by username or email
        user = users_collection.find_one({
            "$or": [
                {"email": {"$regex": f"^{re.escape(identifier)}$", "$options": "i"}},
                {"username": {"$regex": f"^{re.escape(identifier)}$", "$options": "i"}}
            ]
        })

        if not user:
            return None

        entered_hash = hash_password(password or "", user.get("password_salt", ""))

        if not hmac.compare_digest(entered_hash, user.get("password_hash", "")):
            return None

        display_name = user.get("full_name") or user.get("name") or "User"
        return {
            "id": str(user["_id"]),
            "username": user.get("username", ""),
            "name": display_name,
            "email": user.get("email", ""),
            "role": user.get("role", "User"),
            "status": user.get("status", "Active"),
        }

    except Exception:
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
        "username": app.storage.user.get("user_username", ""),
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

            # Users can enter either their email or username
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
                app.storage.user["user_role"] = user["role"]
                app.storage.user["user_status"] = user["status"]

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
