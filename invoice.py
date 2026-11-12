import sqlite3
from pathlib import Path
from nicegui import ui

DB = Path(__file__).with_name("nexora.db")

def connect():
    con = sqlite3.connect(DB, timeout=15)
    con.row_factory = sqlite3.Row
    return con

def setup_invoice_database():
    with connect() as con:
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
        # अगर टेबल खाली है तो डिफ़ॉल्ट सैंपल एंट्री जोड़ें ताकि कभी खाली न दिखे
        cnt = con.execute("SELECT COUNT(*) as c FROM invoices").fetchone()["c"]
        if cnt == 0:
            con.execute(
                "INSERT INTO invoices (client_name, service_item, amount, status) VALUES (?, ?, ?, ?)",
                ("Acme Corp", "Software Consultation & Setup", 15000.00, "Unpaid")
            )

def render_invoice_module():
    setup_invoice_database()

    with ui.column().classes("w-full min-h-full gap-6 p-6 bg-slate-950 text-white"):
        ui.label("🧾 NEXORA Invoicing & Billing Hub").style("font-size:24px; font-weight:800; color:white;")
        ui.label("Create professional client invoices, track payments, and manage billings.").style("color:#94a3b8; font-size:13px;")

        # 1. Create Invoice Form Card
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

        # 2. Invoices Directory List Card
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