import hashlib
import hmac
import secrets
import sqlite3
from pathlib import Path
from nicegui import app, ui

try:
    import auth
except Exception:
    auth = None

DB = Path(__file__).with_name("nexora.db")


def connect():
    con = sqlite3.connect(DB, timeout=15)
    con.row_factory = sqlite3.Row
    return con


def hash_password(password: str, salt: str = "") -> str:
    if salt:
        return hashlib.pbkdf2_hmac(
            "sha256",
            (password or "").encode("utf-8"),
            salt.encode("utf-8"),
            310000,
        ).hex()
    return hashlib.sha256((password or "").encode("utf-8")).hexdigest()


def verify_user_password(user_row: dict, entered_password: str) -> bool:
    pwd = entered_password or ""
    stored_hash = user_row.get("password_hash") or ""
    stored_salt = user_row.get("password_salt") or ""

    if stored_hash:
        if stored_salt and hmac.compare_digest(hash_password(pwd, stored_salt), stored_hash):
            return True
        if hmac.compare_digest(hash_password(pwd, ""), stored_hash):
            return True

    if user_row.get("password"):
        return hmac.compare_digest(str(user_row["password"]), pwd)

    return False


def set_active_session_user(user_info: dict, app_storage=None, auth_module=None):
    storage = app_storage if app_storage is not None else app.storage.user
    mod = auth_module if auth_module is not None else auth

    email = (user_info.get("email") or "").strip().lower()
    username = (user_info.get("username") or "").strip()
    phone = (
        user_info.get("phone")
        or user_info.get("mobile")
        or user_info.get("contact")
        or ""
    ).strip()
    full_name = (
        user_info.get("full_name")
        or user_info.get("name")
        or username
        or (email.split("@")[0] if email else "User")
    ).strip()
    role = (user_info.get("role") or "User").strip()
    status = (user_info.get("status") or "Active").strip()
    uid = user_info.get("id")

    storage["user_id"] = uid
    storage["user_email"] = email
    storage["user_username"] = username
    storage["user_phone"] = phone
    storage["user_name"] = full_name
    storage["user_role"] = role
    storage["user_status"] = status

    if mod is not None:
        try:
            mod._CURRENT_USER = {
                "id": uid,
                "email": email,
                "username": username,
                "phone": phone,
                "name": full_name,
                "full_name": full_name,
                "role": role,
                "status": status,
            }
        except Exception:
            pass


def get_session_user() -> dict:
    u = {}
    if auth is not None:
        try:
            for attr_name in ("_CURRENT_USER", "current_user_data", "active_user_data"):
                val = getattr(auth, attr_name, None)
                if isinstance(val, dict) and val:
                    u = dict(val)
                    break
            if not u and callable(getattr(auth, "current_user", None)):
                raw = auth.current_user()
                if isinstance(raw, dict) and raw:
                    u = dict(raw)
        except Exception:
            u = {}

    email = (u.get("email") or app.storage.user.get("user_email") or "").strip().lower()
    username = (u.get("username") or app.storage.user.get("user_username") or "").strip()
    phone = (
        u.get("phone")
        or u.get("mobile")
        or u.get("contact")
        or app.storage.user.get("user_phone")
        or ""
    ).strip()
    name = (
        u.get("name")
        or u.get("full_name")
        or app.storage.user.get("user_name")
        or username
        or ""
    ).strip()

    return {
        "id": u.get("id") if u.get("id") is not None else app.storage.user.get("user_id"),
        "username": username,
        "name": name,
        "email": email,
        "phone": phone,
        "role": (u.get("role") or app.storage.user.get("user_role") or "User").strip(),
        "status": (u.get("status") or app.storage.user.get("user_status") or "Active").strip(),
    }


def setup_profile_database():
    with connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                name TEXT,
                full_name TEXT,
                email TEXT UNIQUE,
                phone TEXT DEFAULT '',
                role TEXT DEFAULT 'User',
                status TEXT DEFAULT 'Active',
                password_hash TEXT,
                password_salt TEXT,
                theme TEXT DEFAULT 'Dark'
            )
        """)
        cols = {r["name"] for r in con.execute("PRAGMA table_info(users)")}
        for col, ddl in [
            ("theme", "ALTER TABLE users ADD COLUMN theme TEXT DEFAULT 'Dark'"),
            ("phone", "ALTER TABLE users ADD COLUMN phone TEXT DEFAULT ''"),
            ("full_name", "ALTER TABLE users ADD COLUMN full_name TEXT"),
        ]:
            if col not in cols:
                try:
                    con.execute(ddl)
                except Exception:
                    pass


def get_current_db_user(session_user: dict) -> dict | None:
    uid = session_user.get("id")
    email = (session_user.get("email") or "").strip().lower()
    username = (session_user.get("username") or "").strip().lower()
    phone = (session_user.get("phone") or "").strip()
    name = (session_user.get("name") or "").strip()

    if not uid and not email and not username and not phone and not name:
        return None

    row_dict = None
    with connect() as con:
        if email:
            row = con.execute(
                "SELECT * FROM users WHERE LOWER(TRIM(email)) = ?",
                (email,),
            ).fetchone()
            if row:
                row_dict = dict(row)
        if not row_dict and username:
            row = con.execute(
                "SELECT * FROM users WHERE LOWER(TRIM(username)) = ?",
                (username,),
            ).fetchone()
            if row:
                row_dict = dict(row)
        if not row_dict and uid is not None and str(uid).strip() != "":
            row = con.execute(
                "SELECT * FROM users WHERE CAST(id AS TEXT) = ?",
                (str(uid).strip(),),
            ).fetchone()
            if row:
                row_dict = dict(row)

    if row_dict is not None:
        if phone and not (row_dict.get("phone") or "").strip():
            row_dict["phone"] = phone
        if name and not (row_dict.get("full_name") or row_dict.get("name") or "").strip():
            row_dict["full_name"] = name
            row_dict["name"] = name
        return row_dict

    if email or username or name or phone:
        display_name = name or username or (email.split("@")[0] if email else "User")
        return {
            "id": uid,
            "username": username or display_name,
            "name": display_name,
            "full_name": display_name,
            "email": email,
            "phone": phone,
            "role": session_user.get("role") or "User",
            "theme": app.storage.user.get("theme") or "Dark",
        }
    return None


def delete_user_account(target_id=None, target_email: str = ""):
    current_uid = str(app.storage.user.get("user_id") or "").strip()
    current_email = str(app.storage.user.get("user_email") or "").strip().lower()
    clean_email = (target_email or "").strip().lower()

    is_self_delete = bool(
        (target_id is not None and current_uid and str(target_id).strip() == current_uid)
        or (clean_email and current_email and clean_email == current_email)
    )

    try:
        with connect() as con:
            if target_id is not None and str(target_id).strip() != "":
                con.execute("DELETE FROM users WHERE CAST(id AS TEXT) = ?", (str(target_id).strip(),))
            elif clean_email:
                con.execute("DELETE FROM users WHERE LOWER(TRIM(email)) = ?", (clean_email,))
            else:
                ui.notify("No account specified to delete.", color="warning")
                return
            con.commit()

        ui.notify("Account deleted successfully!", color="positive")

        if is_self_delete:
            app.storage.user.clear()
            if auth is not None:
                try:
                    auth._CURRENT_USER = None
                except Exception:
                    pass
            ui.navigate.to("/login")
        else:
            ui.navigate.reload()
    except Exception as e:
        ui.notify(f"Could not delete account: {e}", color="negative")
def apply_theme_mode(theme_name: str):
    chosen = "Light" if (theme_name or "").strip().lower() == "light" else "Dark"
    app.storage.user["theme"] = chosen
    dm = ui.dark_mode()
    if chosen == "Light":
        dm.disable()
    else:
        dm.enable()

    ui.add_head_html("""
    <style id="nexora-theme-override">
        body, .q-page, .q-layout, .nicegui-content,
        header, .q-header, .q-toolbar, .q-drawer,
        .q-tabs, .q-tab-panels, .q-tab-panel {
            background-color: #0b1f3a !important;
            color: #ffffff !important;
        }

        header, .q-header, .q-toolbar {
            background-color: #0b1f3a !important;
        }

        header *, .q-header *, .q-toolbar *,
        .q-tabs .q-tab, .q-tabs .q-tab *, [role="tab"], [role="tab"] * {
            color: #ffffff !important;
        }

        .nexora-brand-title, .nexora-brand-title * {
            color: #0b1f3a !important;
        }

        .q-tab--active, [aria-selected="true"] {
            background-color: #16365f !important;
            border-bottom: 3px solid #60a5fa !important;
        }

        .q-card, .n-card, .bg-slate-900, .bg-dark {
            background-color: #ffffff !important;
            color: #0b1f3a !important;
            border: 1px solid #cbd5e1 !important;
        }
        .q-card *, .n-card *, .bg-slate-900 *, .bg-dark * {
            color: #0b1f3a !important;
        }
    </style>
    """)


def render_profile_settings():
    setup_profile_database()

    session_user = get_session_user()
    db_user = get_current_db_user(session_user)

    if not db_user:
        with ui.column().classes("w-full gap-4 p-4"):
            ui.label("⚙️ Profile & System Settings").style("font-size:24px; font-weight:800; color:#ffffff;")
            ui.label("Active user account not found. Please log out and log in again.").style("color:#fca5a5; font-weight:600;")
        return

    merged = dict(db_user)
    full_name = (
        session_user.get("name")
        or merged.get("full_name")
        or merged.get("name")
        or merged.get("username")
        or "User"
    ).strip()
    email = (session_user.get("email") or merged.get("email") or "").strip().lower()
    phone = (session_user.get("phone") or merged.get("phone") or "").strip()
    raw_role = (session_user.get("role") or merged.get("role") or "User").strip()
    role_lower = raw_role.lower()

    if role_lower in ("admin", "administrator", "system administrator"):
        role_display = "Admin"
        badge_color = "blue"
    elif role_lower == "manager":
        role_display = "Manager"
        badge_color = "purple"
    else:
        role_display = "User"
        badge_color = "teal"

    saved_theme = merged.get("theme") or app.storage.user.get("theme") or "Dark"
    current_theme = "Light" if str(saved_theme).strip().lower() == "light" else "Dark"
    apply_theme_mode(current_theme)

    card_cls = "bg-white text-slate-900 border-slate-300"

    with ui.column().classes("w-full gap-6 p-4"):
        ui.label("⚙️ Profile & System Settings").style("font-size:24px; font-weight:800; color:#ffffff;")
        ui.label("Manage your personal information, security preferences, and display settings.").style(
            "color:#e2e8f0; font-size:13px;"
        )

        with ui.row().classes("w-full gap-6 items-start flex-col md:flex-row"):
            with ui.card().classes(f"w-full md:w-80 p-6 border items-center text-center {card_cls}"):
                ui.avatar("person", size="80px", color="primary", text_color="white").classes("mb-2")
                ui.label(full_name).style("font-size:18px; font-weight:700; color:#0b1f3a;")
                ui.label(role_display).style("font-size:12px; color:#1d4ed8; font-weight:600;")
                ui.badge(role_display, color=badge_color).classes("mt-1")
                ui.label(f"✉️ {email}" if email else "✉️ No email").style("font-size:12px; color:#334155; margin-top:8px;")
                ui.label(f"📞 {phone}" if phone else "📞 No phone").style("font-size:12px; color:#334155;")
                ui.badge("Active Profile", color="green").classes("mt-4")

            with ui.card().classes(f"flex-1 w-full p-6 border {card_cls}"):
                ui.label("👤 Personal Information").style("font-size:16px; font-weight:700; color:#0b1f3a;")
                ui.label("Update your account details and contact info.").style("font-size:12px; color:#334155; margin-bottom:12px;")

                name_in = ui.input("Full Name", value=full_name).props("outlined dense").classes("w-full mb-3 text-slate-900")
                email_in = ui.input("Email Address", value=email).props("outlined dense").classes("w-full mb-3 text-slate-900")
                phone_in = ui.input("Phone Number", value=phone).props("outlined dense").classes("w-full mb-4 text-slate-900")

                def update_personal_info():
                    new_name = (name_in.value or "").strip()
                    new_email = (email_in.value or "").strip().lower()
                    new_phone = (phone_in.value or "").strip()

                    if not new_name or not new_email:
                        ui.notify("Name and Email cannot be empty!", color="negative")
                        return

                    try:
                        with connect() as con:
                            cols = {r["name"] for r in con.execute("PRAGMA table_info(users)")}
                            set_parts, params = [], []
                            for field, val in [
                                ("full_name", new_name),
                                ("name", new_name),
                                ("email", new_email),
                                ("phone", new_phone),
                            ]:
                                if field in cols:
                                    set_parts.append(f"{field} = ?")
                                    params.append(val)

                            if merged.get("id") is not None:
                                params.append(merged["id"])
                                con.execute(f"UPDATE users SET {', '.join(set_parts)} WHERE id = ?", params)
                            elif email:
                                params.append(email.lower())
                                con.execute(f"UPDATE users SET {', '.join(set_parts)} WHERE LOWER(email) = ?", params)
                            con.commit()

                        app.storage.user["user_name"] = new_name
                        app.storage.user["user_email"] = new_email
                        app.storage.user["user_phone"] = new_phone
                        if auth is not None and isinstance(getattr(auth, "_CURRENT_USER", None), dict):
                            auth._CURRENT_USER["name"] = new_name
                            auth._CURRENT_USER["full_name"] = new_name
                            auth._CURRENT_USER["email"] = new_email
                            auth._CURRENT_USER["phone"] = new_phone

                        ui.notify("Personal information updated successfully!", color="positive")
                        ui.navigate.reload()
                    except Exception as e:
                        ui.notify(f"Could not update profile: {e}", color="negative")

                with ui.row().classes("gap-3 items-center flex-wrap"):
                    ui.button("Save Changes", on_click=update_personal_info).props("color=primary")
                    ui.button(
                        "Delete Account",
                        on_click=lambda: delete_user_account(merged.get("id"), email),
                    ).props("outline color=negative")

        with ui.row().classes("w-full gap-6 items-start flex-col md:flex-row"):
            with ui.card().classes(f"flex-1 w-full p-6 border {card_cls}"):
                ui.label("🔒 Security & Password Change").style("font-size:16px; font-weight:700; color:#0b1f3a;")
                ui.label("Ensure your account is secure by using a strong password.").style("font-size:12px; color:#334155; margin-bottom:12px;")

                old_pass = ui.input("Current Password", password=True, password_toggle_button=True).props("outlined dense").classes("w-full mb-3 text-slate-900")
                new_pass = ui.input("New Password", password=True, password_toggle_button=True).props("outlined dense").classes("w-full mb-4 text-slate-900")

                def change_password():
                    op = (old_pass.value or "").strip()
                    np = (new_pass.value or "").strip()

                    if not op or not np:
                        ui.notify("Please fill both password fields!", color="negative")
                        return
                    if len(np) < 6:
                        ui.notify("New password must be at least 6 characters!", color="warning")
                        return

                    fresh_user = get_current_db_user(get_session_user()) or merged
                    if not fresh_user or not verify_user_password(fresh_user, op):
                        ui.notify("Current password is incorrect!", color="negative")
                        return

                    new_salt = secrets.token_hex(16)
                    new_hash = hash_password(np, new_salt)

                    try:
                        with connect() as con:
                            cols = {r["name"] for r in con.execute("PRAGMA table_info(users)")}
                            set_parts, params = [], []
                            for field, val in [("password_hash", new_hash), ("password_salt", new_salt), ("password", np)]:
                                if field in cols:
                                    set_parts.append(f"{field} = ?")
                                    params.append(val)

                            if fresh_user.get("id") is not None:
                                params.append(fresh_user["id"])
                                con.execute(f"UPDATE users SET {', '.join(set_parts)} WHERE id = ?", params)
                            elif email:
                                params.append(email.lower())
                                con.execute(f"UPDATE users SET {', '.join(set_parts)} WHERE LOWER(email) = ?", params)
                            con.commit()

                        merged["password_hash"] = new_hash
                        merged["password_salt"] = new_salt
                        ui.notify("Password changed successfully!", color="positive")
                        old_pass.value, new_pass.value = "", ""
                    except Exception as e:
                        ui.notify(f"Error changing password: {e}", color="negative")

                ui.button("Update Password", on_click=change_password).props("color=orange").classes("text-white")

            with ui.card().classes(f"flex-1 w-full p-6 border {card_cls}"):
                ui.label("🎨 Display & Theme Preferences").style("font-size:16px; font-weight:700; color:#0b1f3a;")
                ui.label("Customize your workspace look and feel.").style("font-size:12px; color:#334155; margin-bottom:16px;")

                theme_select = ui.select(["Dark", "Light"], value=current_theme, label="Interface Theme").props("outlined dense").classes("w-full mb-6 text-slate-900")

                def save_theme():
                    chosen_theme = theme_select.value or "Dark"
                    try:
                        with connect() as con:
                            cols = {r["name"] for r in con.execute("PRAGMA table_info(users)")}
                            if "theme" in cols:
                                if merged.get("id") is not None:
                                    con.execute("UPDATE users SET theme = ? WHERE id = ?", (chosen_theme, merged["id"]))
                                elif email:
                                    con.execute("UPDATE users SET theme = ? WHERE LOWER(email) = ?", (chosen_theme, email.lower()))
                                con.commit()
                    except Exception:
                        pass

                    apply_theme_mode(chosen_theme)
                    ui.notify(f"Theme switched to {chosen_theme}!", color="info")
                    ui.navigate.reload()

                ui.button("Apply Theme", on_click=save_theme).props("outline color=emerald")
