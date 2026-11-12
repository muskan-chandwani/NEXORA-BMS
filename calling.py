import sqlite3
from pathlib import Path
from nicegui import ui

DB = Path(__file__).with_name("nexora.db")

def connect():
    con = sqlite3.connect(DB, timeout=15)
    con.row_factory = sqlite3.Row
    return con

def setup_calling_database():
    with connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS nexora_contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                relation TEXT DEFAULT 'Client',
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS call_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                call_type TEXT DEFAULT 'Outgoing',
                timestamp TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)
        # Default contact if table is empty
        cnt = con.execute("SELECT COUNT(*) as c FROM nexora_contacts").fetchone()["c"]
        if cnt == 0:
            con.execute(
                "INSERT INTO nexora_contacts (name, phone, relation) VALUES (?, ?, ?)",
                ("Support Desk", "+919876543210", "Support")
            )

def render_calling_module():
    setup_calling_database()

    with ui.column().classes("w-full gap-6 p-4"):
        # Header
        ui.label("📞 NEXORA Business Calling & Communication Hub").style("font-size:24px; font-weight:800; color:white;")
        ui.label("Manage business contacts, place calls, and track communication history.").style("color:#94a3b8; font-size:13px;")

        # Top Row: Add Contact & Quick Dial
        with ui.row().classes("w-full gap-4 items-start"):
            
            # Add Contact Card
            with ui.card().classes("flex-1 p-5 bg-slate-900 border border-slate-700"):
                ui.label("➕ Add New Business Contact").style("font-size:16px; font-weight:700; color:white;")
                
                c_name = ui.input(placeholder="Contact Name").props("outlined dark dense").classes("w-full mt-2 text-white")
                c_phone = ui.input(placeholder="Phone Number (+91...)").props("outlined dark dense").classes("w-full mt-2 text-white")
                c_rel = ui.select(["Client", "Vendor", "Partner", "Support"], value="Client", label="Category").props("outlined dark dense").classes("w-full mt-2 text-white")

                def save_contact():
                    name = (c_name.value or "").strip()
                    phone = (c_phone.value or "").strip()
                    if not name or not phone:
                        ui.notify("Name and phone are required!", color="negative")
                        return
                    with connect() as con:
                        con.execute(
                            "INSERT INTO nexora_contacts (name, phone, relation) VALUES (?, ?, ?)",
                            (name, phone, c_rel.value)
                        )
                    ui.notify(f"Contact {name} saved successfully!", color="positive")
                    c_name.value, c_phone.value = "", ""
                    ui.navigate.reload()

                ui.button("Save Contact", icon="person_add", on_click=save_contact).props("color=primary").classes("w-full mt-3")

            # Quick Dial Card
            with ui.card().classes("flex-1 p-5 bg-slate-900 border border-slate-700"):
                ui.label("⚡ Quick Dial / Place Call").style("font-size:16px; font-weight:700; color:white;")
                
                dial_input = ui.input(placeholder="Enter Phone Number or Name").props("outlined dark dense").classes("w-full mt-3 text-white")

                def make_quick_call():
                    val = (dial_input.value or "").strip()
                    if not val:
                        ui.notify("Please enter a number or name to call!", color="negative")
                        return
                    with connect() as con:
                        con.execute(
                            "INSERT INTO call_logs (contact_name, phone, call_type) VALUES (?, ?, ?)",
                            ("Direct Dial", val, "Outgoing")
                        )
                    ui.notify(f"📞 Calling {val}...", color="positive")
                    dial_input.value = ""
                    ui.navigate.reload()

                ui.button("Call Now", icon="phone", on_click=make_quick_call).props("color=emerald").classes("w-full mt-10")

        # Contacts Directory
        with ui.card().classes("w-full p-5 bg-slate-900 border border-slate-700"):
            ui.label("📇 Saved Contacts Directory").style("font-size:16px; font-weight:700; color:white; margin-bottom:8px;")
            
            with connect() as con:
                contacts = con.execute("SELECT * FROM nexora_contacts ORDER BY id DESC").fetchall()

            if not contacts:
                ui.label("No contacts saved yet.").style("color:#94a3b8;")

            for c in contacts:
                cid = c["id"]
                cname = c["name"]
                cph = c["phone"]

                with ui.row().classes("w-full justify-between items-center p-2 bg-slate-950 border border-slate-800 rounded mb-1"):
                    with ui.row().classes("items-center gap-3"):
                        ui.icon("account_circle", color="primary").style("font-size:28px;")
                        with ui.column().classes("gap-0"):
                            ui.label(cname).style("font-weight:bold; color:white;")
                            ui.label(f"📞 {cph}  •  {c['relation']}").style("font-size:12px; color:#94a3b8;")

                    with ui.row().classes("gap-2"):
                        def call_contact(name=cname, ph=cph):
                            with connect() as con:
                                con.execute(
                                    "INSERT INTO call_logs (contact_name, phone, call_type) VALUES (?, ?, ?)",
                                    (name, ph, "Outgoing")
                                )
                            ui.notify(f"📞 Calling {name} ({ph})...", color="positive")
                            ui.navigate.reload()

                        ui.button(icon="phone", on_click=call_contact).props("flat color=green dense")

                        def delete_contact(id_val=cid):
                            with connect() as con:
                                con.execute("DELETE FROM nexora_contacts WHERE id = ?", (id_val,))
                            ui.notify("Contact deleted!", color="negative")
                            ui.navigate.reload()

                        ui.button(icon="delete", on_click=delete_contact).props("flat color=red dense")

        # Call History
        with ui.card().classes("w-full p-5 bg-slate-900 border border-slate-700"):
            ui.label("📜 Recent Call History").style("font-size:16px; font-weight:700; color:white; margin-bottom:8px;")
            
            with connect() as con:
                logs = con.execute("SELECT * FROM call_logs ORDER BY id DESC LIMIT 5").fetchall()

            if not logs:
                ui.label("No call logs recorded yet.").style("color:#94a3b8; font-size:13px;")

            for lg in logs:
                with ui.row().classes("w-full justify-between items-center py-2 border-b border-slate-800"):
                    ui.label(f"📞 {lg['contact_name']} ({lg['phone']})").style("font-size:13px; color:#e2e8f0;")
                    ui.label(lg["timestamp"]).style("font-size:12px; color:#64748b;")