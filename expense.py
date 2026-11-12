import sqlite3
import requests
from pathlib import Path
from datetime import datetime
from nicegui import ui

DB = Path(__file__).with_name("nexora.db")

def connect():
    con = sqlite3.connect(DB, timeout=15)
    con.row_factory = sqlite3.Row
    return con

def setup_expense_database():
    with connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT CHECK(type IN ('Income', 'Expense')) NOT NULL,
                title TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT DEFAULT 'General',
                date TEXT DEFAULT (date('now'))
            )
        """)

# Fetch live gold/silver rates safely
def fetch_metal_rates():
    try:
        res = requests.get("https://api.exchangerate-api.com/v4/latest/INR", timeout=4).json()
        usd_inr = res.get("rates", {}).get("USD", 83.5)
        gold_rate_10g = round((2650 * usd_inr) / 31.1035 * 10, 2)
        silver_rate_1kg = round((31.5 * usd_inr) * 32.1507, 2)
        return gold_rate_10g, silver_rate_1kg
    except Exception:
        return 78500.00, 92000.00

def render_expense_tracker():
    setup_expense_database()

    ui.label("NEXORA Financial & Expense Manager").style("font-size:24px;font-weight:800;color:white")
    ui.label("Track daily expenses, monthly budget, income, charts, and live metal rates.").style("color:#9eafca")

    # Safe rates unpacking
    rates = fetch_metal_rates()
    if isinstance(rates, tuple) and len(rates) == 2:
        gold_price, silver_price = rates
    else:
        gold_price, silver_price = 78500.00, 92000.00

    # 1. LIVE GOLD & SILVER RATES BANNER
    with ui.row().classes("w-full gap-4 mb-4"):
        with ui.card().classes("flex-1 p-3").style("background: linear-gradient(135deg, #b45309, #78350f); color: white;"):
            ui.label("🏆 Gold Rate (24K / 10g)").style("font-size:12px; font-weight:600;")
            ui.label(f"₹ {gold_price:,.2f}").style("font-size:20px; font-weight:800;")
        
        with ui.card().classes("flex-1 p-3").style("background: linear-gradient(135deg, #475569, #1e293b); color: white;"):
            ui.label("🪙 Silver Rate (1 Kg)").style("font-size:12px; font-weight:600;")
            ui.label(f"₹ {silver_price:,.2f}").style("font-size:20px; font-weight:800;")

    # SUMMARY CONTAINERS
    summary_row = ui.row().classes("w-full gap-4 mb-4")

    # 2. INPUT FORM CONTAINER
    with ui.row().classes("w-full gap-3 items-center n-card p-4 mb-4 bg-slate-800 rounded"):
        trans_type = ui.select(["Expense", "Income"], value="Expense", label="Type").props("outlined dark").classes("w-32 text-white")
        title_input = ui.input(placeholder="Description (e.g. Salary, Rent)").props("outlined dark").classes("flex-1 text-white")
        amount_input = ui.input(placeholder="Amount (₹)").props("outlined dark type=number").classes("w-32 text-white")
        category_select = ui.select(["General", "Salary", "Food/Bills", "Operations", "Shopping", "Investment"], value="General", label="Category").props("outlined dark").classes("w-40 text-white")
        date_input = ui.input(placeholder="YYYY-MM-DD", value=datetime.now().strftime("%Y-%m-%d")).props("outlined dark").classes("w-36 text-white")

        def add_transaction():
            t_type = trans_type.value
            title = (title_input.value or "").strip()
            raw_amt = amount_input.value

            if not title or not raw_amt:
                ui.notify("Please enter valid details!", color="negative")
                return

            try:
                amt = float(raw_amt)
            except ValueError:
                ui.notify("Amount must be a number!", color="negative")
                return

            with connect() as con:
                con.execute(
                    "INSERT INTO transactions (type, title, amount, category, date) VALUES (?, ?, ?, ?, ?)",
                    (t_type, title, amt, category_select.value, date_input.value)
                )

            title_input.value = ""
            amount_input.value = ""
            ui.notify("Recorded successfully!", color="positive")
            refresh_all()

        ui.button("Add", icon="add", on_click=add_transaction).props("color=primary").classes("h-12")

    # 3. LIST & CHART LAYOUT
    content_row = ui.row().classes("w-full gap-4 items-start")

    def refresh_all():
        summary_row.clear()
        content_row.clear()

        with connect() as con:
            rows = con.execute("SELECT * FROM transactions ORDER BY date DESC, id DESC").fetchall()

        total_income = sum(r["amount"] for r in rows if r["type"] == "Income")
        total_expense = sum(r["amount"] for r in rows if r["type"] == "Expense")
        balance = total_income - total_expense

        # Summary Cards
        with summary_row:
            with ui.card().classes("flex-1 p-4").style("background:#10b981; color:white;"):
                ui.label("Total Income").style("font-size:12px; font-weight:600;")
                ui.label(f"₹ {total_income:,.2f}").style("font-size:20px; font-weight:800;")
            with ui.card().classes("flex-1 p-4").style("background:#ef4444; color:white;"):
                ui.label("Total Expense").style("font-size:12px; font-weight:600;")
                ui.label(f"₹ {total_expense:,.2f}").style("font-size:20px; font-weight:800;")
            with ui.card().classes("flex-1 p-4").style("background:#2563eb; color:white;"):
                ui.label("Net Balance").style("font-size:12px; font-weight:600;")
                ui.label(f"₹ {balance:,.2f}").style("font-size:20px; font-weight:800;")

        with content_row:
            # Transaction History List
            with ui.column().classes("flex-1 gap-2"):
                ui.label("Recent Transactions").style("font-size:16px; font-weight:700; color:white;")
                if not rows:
                    ui.label("No transactions recorded yet.").style("color:#9eafca;")
                for r in rows:
                    color = "#10b981" if r["type"] == "Income" else "#ef4444"
                    sign = "+" if r["type"] == "Income" else "-"
                    with ui.card().classes("w-full p-3 flex-row items-center justify-between bg-slate-800"):
                        with ui.column().classes("gap-0"):
                            ui.label(r["title"]).style("font-size:14px; color:white; font-weight:600;")
                            ui.label(f"{r['category']} | {r['date']}").style("font-size:11px; color:#9eafca;")
                        with ui.row().classes("items-center gap-3"):
                            ui.label(f"{sign} ₹ {r['amount']:,.2f}").style(f"font-size:14px; color:{color}; font-weight:700;")
                            
                            def delete_tx(t_id=r["id"]):
                                with connect() as con:
                                    con.execute("DELETE FROM transactions WHERE id = ?", (t_id,))
                                refresh_all()
                            ui.button(icon="delete", on_click=delete_tx).props("flat color=red").classes("p-1")

            # Chart Representation
            with ui.column().classes("w-80 gap-2"):
                ui.label("Expense Breakdown").style("font-size:16px; font-weight:700; color:white;")
                cat_expenses = {}
                for r in rows:
                    if r["type"] == "Expense":
                        cat_expenses[r["category"]] = cat_expenses.get(r["category"], 0) + r["amount"]

                if cat_expenses:
                    chart_options = {
                        'title': {'text': 'Expenses by Category', 'left': 'center', 'textStyle': {'color': '#fff'}},
                        'tooltip': {'trigger': 'item'},
                        'series': [{
                            'type': 'pie',
                            'radius': '60%',
                            'data': [{'name': k, 'value': v} for k, v in cat_expenses.items()],
                        }]
                    }
                    ui.echart(chart_options).classes("w-full h-64")
                else:
                    ui.label("Add expenses to see chart.").style("color:#9eafca;")

    refresh_all()