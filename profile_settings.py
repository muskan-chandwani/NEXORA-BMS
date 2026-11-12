import sqlite3
import hashlib
from pathlib import Path
from nicegui import ui

DB = Path(__file__).with_name("nexora.db")

def connect():
    con = sqlite3.connect(DB, timeout=15)
    con.row_factory = sqlite3.Row
    return con

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def setup_profile_database():
    with connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT DEFAULT '',
                role TEXT DEFAULT 'Administrator',
                password_hash TEXT NOT NULL,
                theme TEXT DEFAULT 'Dark'
            )
        """)
        cnt = con.execute("SELECT COUNT(*) as c FROM user_profile").fetchone()["c"]
        if cnt == 0:
            con.execute(
                "INSERT INTO user_profile (full_name, email, phone, role, password_hash, theme) VALUES (?, ?, ?, ?, ?, ?)",
                ("Muskaan Chandwani", "admin@nexora.in", "+91 9876543210", "System Administrator", hash_password("admin123"), "Dark")
            )

def render_profile_settings():
    setup_profile_database()

    with ui.column().classes("w-full gap-6 p-4"):
        ui.label("⚙️ Profile & System Settings").style("font-size:24px; font-weight:800; color:white;")
        ui.label("Manage your personal information, security preferences, and display settings.").style("color:#94a3b8; font-size:13px;")

        with connect() as con:
            user = con.execute("SELECT * FROM user_profile LIMIT 1").fetchone()

        current_theme = user["theme"] if user["theme"] in ["Dark", "Light"] else "Dark"

        with ui.row().classes("w-full gap-6 items-start"):
            
            # 1. Profile Photo & Basic Info Card
            with ui.card().classes("w-80 p-6 bg-slate-900 border border-slate-700 items-center text-center"):
                ui.avatar("person", size="80px", color="primary", text_color="white").classes("mb-2")
                ui.label(user["full_name"]).style("font-size:18px; font-weight:700; color:white;")
                ui.label(user["role"]).style("font-size:12px; color:#60a5fa; font-weight:600;")
                ui.label(f"✉️ {user['email']}").style("font-size:12px; color:#94a3b8; margin-top:8px;")
                ui.label(f"📞 {user['phone']}").style("font-size:12px; color:#94a3b8;")

                ui.badge("Active Profile", color="green").classes("mt-4")

            # 2. Personal Information Update Form
            with ui.card().classes("flex-1 p-6 bg-slate-900 border border-slate-700"):
                ui.label("👤 Personal Information").style("font-size:16px; font-weight:700; color:white;")
                ui.label("Update your account details and contact info.").style("font-size:12px; color:#94a3b8; margin-bottom:12px;")

                name_in = ui.input("Full Name", value=user["full_name"]).props("outlined dark dense").classes("w-full mb-3 text-white")
                email_in = ui.input("Email Address", value=user["email"]).props("outlined dark dense").classes("w-full mb-3 text-white")
                phone_in = ui.input("Phone Number", value=user["phone"]).props("outlined dark dense").classes("w-full mb-4 text-white")

                def update_personal_info():
                    new_name = (name_in.value or "").strip()
                    new_email = (email_in.value or "").strip()
                    new_phone = (phone_in.value or "").strip()

                    if not new_name or not new_email:
                        ui.notify("Name and Email cannot be empty!", color="negative")
                        return

                    with connect() as con:
                        con.execute(
                            "UPDATE user_profile SET full_name = ?, email = ?, phone = ? WHERE id = 1",
                            (new_name, new_email, new_phone)
                        )
                    ui.notify("Personal information updated successfully!", color="positive")
                    ui.navigate.reload()

                ui.button("Save Changes", on_click=update_personal_info).props("color=primary")

        with ui.row().classes("w-full gap-6 items-start"):
            
            # 3. Password Change Card
            with ui.card().classes("flex-1 p-6 bg-slate-900 border border-slate-700"):
                ui.label("🔒 Security & Password Change").style("font-size:16px; font-weight:700; color:white;")
                ui.label("Ensure your account is secure by using a strong password.").style("font-size:12px; color:#94a3b8; margin-bottom:12px;")

                old_pass = ui.input("Current Password", password=True, password_toggle_button=True).props("outlined dark dense").classes("w-full mb-3 text-white")
                new_pass = ui.input("New Password", password=True, password_toggle_button=True).props("outlined dark dense").classes("w-full mb-4 text-white")

                def change_password():
                    op = (old_pass.value or "").strip()
                    np = (new_pass.value or "").strip()

                    if not op or not np:
                        ui.notify("Please fill both password fields!", color="negative")
                        return

                    if hash_password(op) != user["password_hash"]:
                        ui.notify("Current password is incorrect!", color="negative")
                        return

                    with connect() as con:
                        con.execute(
                            "UPDATE user_profile SET password_hash = ? WHERE id = 1",
                            (hash_password(np),)
                        )
                    ui.notify("Password changed successfully!", color="positive")
                    old_pass.value, new_pass.value = "", ""

                ui.button("Update Password", on_click=change_password).props("color=orange").classes("text-white")

            # 4. App Preferences & Dark/Light Mode
            with ui.card().classes("flex-1 p-6 bg-slate-900 border border-slate-700"):
                ui.label("🎨 Display & Theme Preferences").style("font-size:16px; font-weight:700; color:white;")
                ui.label("Customize your workspace look and feel.").style("font-size:12px; color:#94a3b8; margin-bottom:16px;")

                theme_select = ui.select(["Dark", "Light"], value=current_theme, label="Interface Theme").props("outlined dark dense").classes("w-full mb-6 text-white")

                def save_theme():
                    chosen_theme = theme_select.value
                    with connect() as con:
                        con.execute("UPDATE user_profile SET theme = ? WHERE id = 1", (chosen_theme,))
                    ui.notify(f"Theme switched to {chosen_theme}!", color="info")

                ui.button("Apply Theme", on_click=save_theme).props("outline color=emerald")