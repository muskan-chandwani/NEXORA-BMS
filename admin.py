import sqlite3
import hashlib
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


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def get_current_user_info():
    if auth is None:
        return {}
    try:
        u = auth.current_user()
        return dict(u) if u else {}
    except Exception:
        return {}


def setup_admin_and_invoice_databases():
    with connect() as con:
        # Users table
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'User',
                status TEXT DEFAULT 'Active',
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)
        # Safe migration if created_at column is missing in older db
        try:
            con.execute("ALTER TABLE users ADD COLUMN created_at TEXT DEFAULT (datetime('now', 'localtime'))")
        except Exception:
            pass

        # Admin logs table
        con.execute("""
            CREATE TABLE IF NOT EXISTS admin_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                target TEXT NOT NULL,
                timestamp TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)
        # Invoices table
        con.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_name TEXT NOT NULL,
                service_item TEXT NOT NULL,
                amount REAL NOT NULL,
                status TEXT DEFAULT 'Unpaid',
                date TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)

        # Seed default admin if empty
        existing = con.execute("SELECT COUNT(*) as cnt FROM users").fetchone()["cnt"]
        if existing == 0:
            con.execute(
                "INSERT INTO users (full_name, email, password_hash, role, status) VALUES (?, ?, ?, ?, ?)",
                ("Muskaan Chandwani", "admin@nexora.in", hash_password("admin123"), "Admin", "Active")
            )
            con.execute(
                "INSERT INTO admin_logs (action, target) VALUES (?, ?)",
                ("SYSTEM_INIT", "Admin Panel Initialized")
            )

        # Seed default invoice if empty so it's never blank
        cnt = con.execute("SELECT COUNT(*) as c FROM invoices").fetchone()["c"]
        if cnt == 0:
            con.execute(
                "INSERT INTO invoices (client_name, service_item, amount, status) VALUES (?, ?, ?, ?)",
                ("Acme Corp", "Software Consultation & Setup", 15000.00, "Unpaid")
            )


def log_action(action: str, target: str):
    with connect() as con:
        con.execute("INSERT INTO admin_logs (action, target) VALUES (?, ?)", (action, target))


def render_admin_panel():
    setup_admin_and_invoice_databases()
    curr_user = get_current_user_info()
    curr_uid = str(curr_user.get("id") or app.storage.user.get("user_id") or "").strip()
    curr_email = (curr_user.get("email") or app.storage.user.get("user_email") or "").strip().lower()

    with ui.column().classes("w-full min-h-full gap-6 p-4 text-white"):
        # 1. Admin Header
        ui.label("🛡️ NEXORA Admin Control Center & Invoicing Hub").style("font-size:24px; font-weight:800; color:white;")
        ui.label("Manage registered users, permissions, monitor metrics, and handle client billings.").style("color:#94a3b8; font-size:13px;")

        # 2. System Metrics Cards
        with connect() as con:
            total_users = con.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
            active_users = con.execute("SELECT COUNT(*) as c FROM users WHERE status='Active'").fetchone()["c"]
            try:
                tx_sum = con.execute("SELECT COALESCE(SUM(amount), 0) as s FROM transactions").fetchone()["s"]
            except:
                tx_sum = 0
            try:
                habit_cnt = con.execute("SELECT COUNT(*) as c FROM habits").fetchone()["c"]
            except:
                habit_cnt = 0

        with ui.row().classes("w-full gap-4"):
            with ui.card().classes("flex-1 p-4 bg-slate-900 border border-slate-700"):
                ui.label("👥 TOTAL USERS").style("font-size:11px; color:#93c5fd; font-weight:bold;")
                ui.label(str(total_users)).style("font-size:24px; font-weight:900; color:white;")
                ui.label(f"{active_users} Active Accounts").style("font-size:12px; color:#60a5fa;")

            with ui.card().classes("flex-1 p-4 bg-slate-900 border border-slate-700"):
                ui.label("💰 EXPENSE VOLUME").style("font-size:11px; color:#6ee7b7; font-weight:bold;")
                ui.label(f"₹{tx_sum:,.0f}").style("font-size:24px; font-weight:900; color:white;")
                ui.label("Logged Transactions").style("font-size:12px; color:#34d399;")

            with ui.card().classes("flex-1 p-4 bg-slate-900 border border-slate-700"):
                ui.label("🔥 ACTIVE HABITS").style("font-size:11px; color:#d8b4fe; font-weight:bold;")
                ui.label(str(habit_cnt)).style("font-size:24px; font-weight:900; color:white;")
                ui.label("Tracked Routines").style("font-size:12px; color:#c084fc;")

        # 3. Register New User Form (Admin Feature)
        with ui.card().classes("w-full p-4 bg-slate-900 border border-slate-700"):
            ui.label("➕ Register New User").style("font-size:16px; font-weight:700; color:white;")
            with ui.row().classes("w-full gap-3 items-center mt-2"):
                name_in = ui.input(placeholder="Full Name").props("outlined dark dense").classes("flex-1 text-white")
                email_in = ui.input(placeholder="Email Address").props("outlined dark dense").classes("flex-1 text-white")
                pass_in = ui.input(placeholder="Password", password=True).props("outlined dark dense").classes("w-40 text-white")
                role_in = ui.select(["User", "Manager", "Admin"], value="User", label="Role").props("outlined dark dense").classes("w-32 text-white")

                def add_user():
                    n = (name_in.value or "").strip()
                    e = (email_in.value or "").strip().lower()
                    p = (pass_in.value or "").strip()
                    if not n or not e or not p:
                        ui.notify("All fields are required!", color="negative")
                        return
                    try:
                        with connect() as con:
                            con.execute(
                                "INSERT INTO users (full_name, email, password_hash, role, status) VALUES (?, ?, ?, ?, 'Active')",
                                (n, e, hash_password(p), role_in.value)
                            )
                        log_action("USER_CREATED", e)
                        ui.notify(f"User {n} created successfully!", color="positive")
                        ui.navigate.reload()
                    except Exception as err:
                        ui.notify(f"Error: {err}", color="negative")

                ui.button("Create User", on_click=add_user).props("color=primary")

        # 4. Registered Users Directory Table (Admin Feature)
        with ui.card().classes("w-full p-4 bg-slate-900 border border-slate-700"):
            ui.label("👥 Registered Users Directory").style("font-size:16px; font-weight:700; color:white; margin-bottom:8px;")

            with connect() as con:
                users = con.execute("SELECT * FROM users ORDER BY id DESC").fetchall()

            for u in users:
                uid = u["id"]
                target_email = (u["email"] or "").strip().lower()

                with ui.row().classes("w-full justify-between items-center py-2 border-b border-slate-800"):
                    with ui.column().classes("gap-0"):
                        with ui.row().classes("items-center gap-2"):
                            ui.label(u["full_name"]).style("font-weight:bold; color:white;")
                            ui.badge(u["role"], color="blue" if u["role"] == "Admin" else "grey")
                            ui.badge(u["status"], color="green" if u["status"] == "Active" else "red")

                        created = u["created_at"] if "created_at" in u.keys() else "N/A"
                        ui.label(f"✉️ {u['email']} | Joined: {created}").style("font-size:12px; color:#94a3b8;")

                    def delete_user(user_id=uid, mail=u["email"], t_mail=target_email):
                        is_self = bool(
                            (curr_uid and str(user_id).strip() == curr_uid)
                            or (curr_email and t_mail and t_mail == curr_email)
                        )
                        with connect() as con:
                            con.execute("DELETE FROM users WHERE id = ?", (user_id,))
                        log_action("USER_DELETED", mail)
                        ui.notify("User deleted!", color="negative")
                        if is_self:
                            app.storage.user.clear()
                            if auth is not None:
                                try:
                                    auth._CURRENT_USER = None
                                except Exception:
                                    pass
                            ui.navigate.to("/login")
                        else:
                            ui.navigate.reload()

                    ui.button(icon="delete", on_click=delete_user).props("flat color=red dense")

        ui.separator().classes("bg-slate-800 my-4")

        # 5. Integrated Invoicing & Billing Section (Invoice Features)
        ui.label("🧾 Integrated Invoicing & Billing Module").style("font-size:20px; font-weight:800; color:white; margin-top:10px;")

        # Create Invoice Form Card
        with ui.card().classes("w-full p-6 bg-slate-900 border border-slate-700"):
            ui.label("➕ Create New Invoice").style("font-size:16px; font-weight:700; color:white; margin-bottom:10px;")

            with ui.row().classes("w-full gap-4 items-center"):
                client_in = ui.input(placeholder="Client Name").props("outlined dark dense").classes("flex-1 text-white")
                item_in = ui.input(placeholder="Service / Product Description").props("outlined dark dense").classes("flex-1 text-white")
                amount_in = ui.number(placeholder="Amount (₹)", format="%.2f").props("outlined dark dense").classes("w-48 text-white")

            def create_invoice():
                client = (client_in.value or "").strip()
                item = (item_in.value or "").strip()
                amt = amount_in.value

                if not client or not item or not amt:
                    ui.notify("Please fill all invoice fields!", color="negative")
                    return

                try:
                    with connect() as con:
                        con.execute(
                            "INSERT INTO invoices (client_name, service_item, amount, status) VALUES (?, ?, ?, 'Unpaid')",
                            (client, item, float(amt))
                        )
                    ui.notify("Invoice generated successfully!", color="positive")
                    client_in.value = ""
                    item_in.value = ""
                    amount_in.value = None
                    ui.navigate.reload()
                except Exception as e:
                    ui.notify(f"Error: {e}", color="negative")

            ui.button("Generate Invoice", on_click=create_invoice).props("color=primary").classes("mt-4")

        # Invoices Directory List Card
        with ui.card().classes("w-full p-6 bg-slate-900 border border-slate-700"):
            ui.label("📋 Issued Invoices Directory").style("font-size:16px; font-weight:700; color:white; margin-bottom:12px;")

            with connect() as con:
                invoices = con.execute("SELECT * FROM invoices ORDER BY id DESC").fetchall()

            if not invoices:
                ui.label("No invoices created yet.").style("color:#94a3b8;")

            for inv in invoices:
                iid = inv["id"]
                is_paid = inv["status"] == "Paid"

                with ui.row().classes("w-full justify-between items-center py-3 border-b border-slate-800"):
                    with ui.column().classes("gap-1"):
                        with ui.row().classes("items-center gap-2"):
                            ui.label(f"#{iid} - {inv['client_name']}").style("font-weight:bold; color:white; font-size:15px;")
                            ui.badge(inv["status"], color="green" if is_paid else "orange")
                        ui.label(f"📦 {inv['service_item']}  •  ₹{inv['amount']:,.2f}  •  📅 {inv['date']}").style("font-size:13px; color:#94a3b8;")

                    with ui.row().classes("gap-2 items-center"):
                        def toggle_status(inv_id=iid, curr_status=inv["status"]):
                            new_st = "Paid" if curr_status == "Unpaid" else "Unpaid"
                            with connect() as con:
                                con.execute("UPDATE invoices SET status = ? WHERE id = ?", (new_st, inv_id))
                            ui.notify(f"Invoice marked as {new_st}!", color="positive")
                            ui.navigate.reload()

                        ui.button("Mark Paid" if not is_paid else "Mark Unpaid", on_click=toggle_status).props("outline dense color=green").classes("text-xs")

                        def delete_invoice(inv_id=iid):
                            with connect() as con:
                                con.execute("DELETE FROM invoices WHERE id = ?", (inv_id,))
                            ui.notify("Invoice deleted.", color="negative")
                            ui.navigate.reload()

                        ui.button(icon="delete", on_click=delete_invoice).props("flat color=red dense")
