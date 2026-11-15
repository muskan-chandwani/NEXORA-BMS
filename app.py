import os
import sqlite3
import re
from pathlib import Path
from datetime import datetime

from nicegui import ui
import auth
import dashboard
import task
import expense 
import admin
import calling
import profile_settings


DB = Path(__file__).with_name("nexora.db")


# --------------------------------------------------
# DATABASE AND SAFE MIGRATIONS
# --------------------------------------------------

def connect():
    con = sqlite3.connect(DB, timeout=15)
    con.row_factory = sqlite3.Row
    return con


def setup_database():
    with connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer TEXT NOT NULL,
                service TEXT,
                amount REAL DEFAULT 0,
                advance REAL DEFAULT 0,
                due_date TEXT,
                status TEXT DEFAULT 'Pending',
                customer_id INTEGER,
                customer_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                due_date TEXT,
                priority TEXT DEFAULT 'Medium',
                status TEXT DEFAULT 'Pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        task_columns = {
            row["name"]
            for row in con.execute("PRAGMA table_info(tasks)")
        }

        for column, definition in [
            ("description", "TEXT"),
            ("due_date", "TEXT"),
            ("priority", "TEXT DEFAULT 'Medium'"),
            ("status", "TEXT DEFAULT 'Pending'"),
            ("created_at", "TIMESTAMP"),
        ]:
            if column not in task_columns:
                con.execute(
                    f"ALTER TABLE tasks ADD COLUMN {column} {definition}"
                )


setup_database()


# --------------------------------------------------
# COMMON HELPERS
# --------------------------------------------------

def valid_customer(name, phone, email):
    if not (name or "").strip():
        return "Customer name is required."

    phone = (phone or "").strip()
    if phone and not re.fullmatch(r"[0-9+\-\s()]{7,20}", phone):
        return "Please enter a valid phone number."

    email = (email or "").strip()
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return "Please enter a valid email address."

    return None


# --------------------------------------------------
# MAIN APPLICATION
# --------------------------------------------------

@ui.page("/")
def home_page():

    if not auth.require_login():
        return

    user = auth.current_user()

    ui.add_head_html("""
    <style>
        body {
            background: #080d1b;
            color: white;
            font-family: Arial, sans-serif;
        }
        .n-card {
            background: #14213b;
            border: 1px solid #2b4168;
            border-radius: 15px;
        }
    </style>
    """)

    with ui.column().classes("w-full p-3 md:p-6").style(
        "background:#080d1b;min-height:100vh"
    ):

        # HEADER
        with ui.row().classes(
            "w-full items-center justify-between"
        ):
            with ui.column().classes("gap-0"):
                ui.label("◆ NEXORA").style(
                    "font-size:27px;font-weight:900;"
                    "letter-spacing:3px;color:white"
                )
                ui.label("BUSINESS MANAGEMENT SYSTEM").style(
                    "font-size:10px;letter-spacing:2px;color:#91a8d0"
                )

            with ui.row().classes("items-center"):
                ui.label(user["name"]).style("color:#c5d5ef")
                ui.button(
                    "Dashboard",
                    on_click=lambda: ui.navigate.to("/dashboard")
                ).props("outline color=primary")
                ui.button(
                    "Logout",
                    on_click=auth.logout
                ).props("outline color=negative")

        ui.separator().classes("my-3")

        tabs = ui.tabs().classes("w-full").props(
            "dark active-color=primary indicator-color=primary"
        )
        with tabs:
            overview_tab = ui.tab("Overview", icon="dashboard")
            customers_tab = ui.tab("Customers", icon="groups")
            orders_tab = ui.tab("Orders", icon="receipt_long")
            tasks_tab = ui.tab("Tasks", icon="task_alt")
            expense_tab = ui.tab("expenses",icon="payments")
            admin_tab = ui.tab("Admin Panel", icon="admin_panel_settings")
            calling_tab = ui.tab("Calling Hub", icon="phone_in_talk")
            profile_tab = ui.tab("profile & settings", icon="manage_accounts")

           
        with ui.tab_panels(tabs, value=overview_tab).classes("w-full").props(
            "animated"
        ):
            # ------------------------------------------
            # OVERVIEW TAB
            # ------------------------------------------

            with ui.tab_panel(overview_tab):
                ui.label("Business Overview").style(
                    "font-size:24px;font-weight:800;color:white"
                )

                overview_area = ui.column().classes("w-full")

                def refresh_overview():
                    overview_area.clear()

                    with connect() as con:
                        customer_count = con.execute(
                            "SELECT COUNT(*) FROM customers"
                        ).fetchone()[0]

                        order_count = con.execute(
                            "SELECT COUNT(*) FROM orders"
                        ).fetchone()[0]

                        task_count = con.execute(
                            "SELECT COUNT(*) FROM tasks WHERE status != 'Completed'"
                        ).fetchone()[0]

                        totals = con.execute("""
                            SELECT
                                COALESCE(SUM(amount), 0),
                                COALESCE(SUM(advance), 0)
                            FROM orders
                        """).fetchone()

                    sales = float(totals[0] or 0)
                    advance = float(totals[1] or 0)
                    pending = sales - advance

                    metrics = [
                        ("Total Customers", customer_count, "#3988ff"),
                        ("Total Orders", order_count, "#a879ff"),
                        ("Pending Tasks", task_count, "#e5b84d"),
                        ("Total Sales", f"₹{sales:,.2f}", "#23c99a"),
                    ]

                    with overview_area:
                        with ui.grid(columns=2).classes("w-full gap-3"):
                            for title, value, color in metrics:
                                with ui.card().classes("n-card w-full p-4"):
                                    ui.label(title).style(
                                        "color:#a9bbd8;font-size:13px"
                                    )
                                    ui.label(str(value)).style(
                                        f"font-size:24px;font-weight:900;color:{color}"
                                    )

                refresh_overview()

            # ------------------------------------------
            # CUSTOMER MANAGEMENT TAB
            # ------------------------------------------

            with ui.tab_panel(customers_tab):
                ui.label("Customer Management").style(
                    "font-size:24px;font-weight:800;color:white"
                )

                with ui.card().classes("n-card w-full p-4 mb-4"):
                    ui.label("Add New Customer").style(
                        "font-size:19px;font-weight:bold;color:white"
                    )

                    c_name = ui.input("Customer Name").props("outlined").classes("w-full")
                    c_phone = ui.input("Mobile Number").props("outlined").classes("w-full")
                    c_email = ui.input("Email Address").props("outlined type=email").classes("w-full")
                    c_address = ui.textarea("Full Address").props("outlined").classes("w-full")
                    customer_message = ui.label("").style("color:#ff8795")

                    ui.button(
                        "Save Customer",
                        icon="person_add",
                        on_click=lambda: add_customer()
                    ).props("color=primary").classes("mt-2")

                customer_search = ui.input("Search by Name or Mobile").props("outlined clearable").classes("w-full")
                customer_count_label = ui.label("").style("color:#9eafca")
                customer_list = ui.column().classes("w-full gap-3 mt-2")

                def refresh_customers():
                    customer_list.clear()
                    term = (customer_search.value or "").strip()

                    with connect() as con:
                        if term:
                            pattern = f"%{term}%"
                            rows = con.execute("""
                                SELECT * FROM customers
                                WHERE name LIKE ? OR phone LIKE ? OR email LIKE ?
                                ORDER BY id DESC
                            """, (pattern, pattern, pattern)).fetchall()
                        else:
                            rows = con.execute("SELECT * FROM customers ORDER BY id DESC").fetchall()
                        total = con.execute("SELECT COUNT(*) FROM customers").fetchone()[0]

                    customer_count_label.text = f"Showing {len(rows)} of {total} customers"

                    with customer_list:
                        for customer in rows:
                            cid = customer["id"]
                            with ui.card().classes("n-card w-full p-3"):
                                with ui.row().classes("w-full items-center justify-between"):
                                    with ui.column().classes("gap-1"):
                                        ui.label(f"Customer #{cid} — {customer['name']}").style("font-size:17px;font-weight:bold;color:white")
                                        ui.label(customer["phone"] or "No mobile").style("color:#a9bbd8")
                                    with ui.row().classes("items-center"):
                                        ui.button(icon="delete", on_click=lambda cid=cid: delete_customer(cid)).props("flat color=negative")

                def add_customer():
                    error = valid_customer(c_name.value, c_phone.value, c_email.value)
                    if error:
                        customer_message.text = error
                        return
                    try:
                        with connect() as con:
                            con.execute("INSERT INTO customers (name, phone, email, address) VALUES (?, ?, ?, ?)",
                                        (c_name.value.strip(), c_phone.value.strip(), c_email.value.strip(), c_address.value.strip()))
                        c_name.value, c_phone.value, c_email.value, c_address.value, customer_message.text = "", "", "", "", ""
                        ui.notify("Customer added successfully!", type="positive")
                        refresh_customers()
                        refresh_overview()
                    except sqlite3.Error as e:
                        ui.notify(f"Error: {e}", type="negative")

                def delete_customer(cid):
                    with connect() as con:
                        con.execute("DELETE FROM customers WHERE id = ?", (cid,))
                    ui.notify("Customer deleted!", type="positive")
                    refresh_customers()
                    refresh_overview()

                customer_search.on_value_change(refresh_customers)
                refresh_customers()
            # ------------------------------------------
            # ORDERS TAB
            # ------------------------------------------

            with ui.tab_panel(orders_tab):
                ui.label("Orders Management").style("font-size:24px;font-weight:800;color:white")
                ui.label("Manage customer orders, services and payments.").style("color:#9eafca")

                with ui.card().classes("n-card w-full p-4 mb-4"):
                    ui.label("Create New Order").style("font-size:19px;font-weight:bold;color:white")

                    with connect() as con:
                        cust_rows = con.execute("SELECT id, name, phone FROM customers ORDER BY name").fetchall()
                    
                    cust_options = {c["id"]: f"{c['name']} ({c['phone'] or 'No Phone'})" for c in cust_rows}

                    o_customer_select = ui.select(
                        options=cust_options,
                        label="Select Customer"
                    ).props("outlined").classes("w-full")

                    o_service = ui.input("Service / Product Name").props("outlined").classes("w-full")
                    
                    with ui.row().classes("w-full gap-3"):
                        o_amount = ui.input("Total Amount (₹)", value="0").props("outlined type=number").classes("flex-1")
                        o_advance = ui.input("Advance Paid (₹)", value="0").props("outlined type=number").classes("flex-1")

                    with ui.row().classes("w-full gap-3 mt-2"):
                        o_due_date = ui.input("Due Date (YYYY-MM-DD)", value=datetime.now().strftime("%Y-%m-%d")).props("outlined").classes("flex-1")
                        o_status = ui.select(["Pending", "In Progress", "Completed"], value="Pending", label="Status").props("outlined").classes("flex-1")

                    order_message = ui.label("").style("color:#ff8795")

                    ui.button(
                        "Save Order",
                        icon="receipt",
                        on_click=lambda: add_order()
                    ).props("color=primary").classes("mt-3")

                order_search = ui.input("Search Orders by Customer Name or Service").props("outlined clearable").classes("w-full")
                order_count_label = ui.label("").style("color:#9eafca")
                order_list = ui.column().classes("w-full gap-3 mt-2")

                def refresh_orders():
                    order_list.clear()
                    term = (order_search.value or "").strip()

                    with connect() as con:
                        if term:
                            pattern = f"%{term}%"
                            rows = con.execute("""
                                SELECT * FROM orders
                                WHERE customer_name LIKE ? OR service LIKE ? OR status LIKE ?
                                ORDER BY id DESC
                            """, (pattern, pattern, pattern)).fetchall()
                        else:
                            rows = con.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
                        
                        total_orders = con.execute("SELECT COUNT(*) FROM orders").fetchone()[0]

                    order_count_label.text = f"Showing {len(rows)} of {total_orders} orders"

                    with order_list:
                        if not rows:
                            ui.label("No orders found.").style("color:#a9bbd8")

                        for order in rows:
                            oid = order["id"]
                            amt = float(order["amount"] or 0)
                            adv = float(order["advance"] or 0)
                            bal = amt - adv

                            with ui.card().classes("n-card w-full p-3"):
                                with ui.row().classes("w-full items-center justify-between"):
                                    with ui.column().classes("gap-1"):
                                        ui.label(f"Order #{oid} — {order['customer_name'] or order['customer']}").style("font-size:17px;font-weight:bold;color:white")
                                        ui.label(f"Service: {order['service'] or 'General'}").style("color:#3988ff")
                                        ui.label(f"Amount: ₹{amt:,.2f} | Advance: ₹{adv:,.2f} | Balance Due: ₹{bal:,.2f}").style("color:#23c99a")
                                        ui.label(f"Due Date: {order['due_date']} | Status: {order['status']}").style("color:#e5b84d;font-size:12px")

                                    with ui.row().classes("items-center"):
                                        ui.button(icon="delete", on_click=lambda oid=oid: delete_order(oid)).props("flat color=negative").tooltip("Delete Order")

                def add_order():
                    if not o_customer_select.value:
                        order_message.text = "Please select a customer."
                        return
                    
                    service_name = (o_service.value or "").strip()
                    if not service_name:
                        order_message.text = "Service name is required."
                        return

                    try:
                        amt = float(o_amount.value or 0)
                        adv = float(o_advance.value or 0)
                    except ValueError:
                        order_message.text = "Please enter valid numbers for amount and advance."
                        return

                    selected_cust_id = o_customer_select.value
                    with connect() as con:
                        c_row = con.execute("SELECT name FROM customers WHERE id = ?", (selected_cust_id,)).fetchone()
                        cust_name = c_row["name"] if c_row else "Unknown"

                        con.execute("""
                            INSERT INTO orders (customer, customer_name, customer_id, service, amount, advance, due_date, status)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (cust_name, cust_name, selected_cust_id, service_name, amt, adv, o_due_date.value, o_status.value))

                    o_service.value = ""
                    o_amount.value = "0"
                    o_advance.value = "0"
                    order_message.text = ""
                    
                    ui.notify("Order created successfully!", type="positive")
                    refresh_orders()
                    refresh_overview()

                def delete_order(oid):
                    with connect() as con:
                        con.execute("DELETE FROM orders WHERE id = ?", (oid,))
                    ui.notify("Order deleted successfully!", type="positive")
                    refresh_orders()
                    refresh_overview()

                order_search.on_value_change(refresh_orders)
                refresh_orders()

               

                # ------------------------------------------
            # EXPENSE & FINANCIAL MANAGER TAB
            # ------------------------------------------
            with ui.tab_panel(expense_tab):
                expense.render_expense_tracker()

            with ui.tab_panel(admin_tab):
              admin.render_admin_panel()

            with ui.tab_panel(calling_tab):
              calling.render_calling_module() 

            with ui.tab_panel(profile_tab):
               profile_settings.render_profile_settings()

               

            # ------------------------------------------
            # SMART TASK MANAGER TAB
            # ------------------------------------------

            with ui.tab_panel(tasks_tab):
                task.render_task_manager()
                ui.label("Smart Task Manager").style("font-size:24px;font-weight:800;color:white")
                ui.label("Organize, track, and manage your daily business tasks.").style("color:#9eafca")

                with ui.card().classes("n-card w-full p-4 mb-4"):
                    ui.label("Add New Task").style("font-size:19px;font-weight:bold;color:white")
                    
                    t_title = ui.input("Task Title").props("outlined").classes("w-full")
                    t_desc = ui.textarea("Description / Notes").props("outlined").classes("w-full")
                    
                    with ui.row().classes("w-full gap-3"):
                        t_date = ui.input("Due Date (YYYY-MM-DD)", value=datetime.now().strftime("%Y-%m-%d")).props("outlined").classes("flex-1")
                        t_priority = ui.select(["High", "Medium", "Low"], value="Medium", label="Priority").props("outlined").classes("flex-1")

                    task_message = ui.label("").style("color:#ff8795")

                    ui.button(
                        "Save Task",
                        icon="add_task",
                        on_click=lambda: add_task()
                    ).props("color=primary").classes("mt-2")

                task_list = ui.column().classes("w-full gap-3")

                def refresh_tasks():
                    task_list.clear()
                    with connect() as con:
                        rows = con.execute("SELECT * FROM tasks ORDER BY id DESC").fetchall()

                    with task_list:
                        if not rows:
                            ui.label("No tasks found. Add a new task above.").style("color:#a9bbd8")
                        
                        for task in rows:
                            tid = task["id"]
                            status = task["status"]
                            color_border = "#23c99a" if status == "Completed" else "#3988ff"

                            with ui.card().classes("n-card w-full p-3").style(f"border-left: 5px solid {color_border}"):
                                with ui.row().classes("w-full items-center justify-between"):
                                    with ui.column().classes("gap-1"):
                                        ui.label(task["title"]).style(
                                            "font-size:17px;font-weight:bold;color:white;" + 
                                            ("text-decoration: line-through; color: #888;" if status == "Completed" else "")
                                        )
                                        if task["description"]:
                                            ui.label(task["description"]).style("color:#a9bbd8;font-size:13px")
                                        ui.label(f"Due: {task['due_date']} | Priority: {task['priority']} | Status: {status}").style("color:#e5b84d;font-size:12px")

                                    with ui.row().classes("items-center"):
                                        if status != "Completed":
                                            ui.button(icon="check", on_click=lambda tid=tid: mark_task_complete(tid)).props("flat color=positive").tooltip("Mark Completed")
                                        else:
                                            ui.button(icon="undo", on_click=lambda tid=tid: mark_task_pending(tid)).props("flat color=warning").tooltip("Mark Pending")
                                        
                                        ui.button(icon="delete", on_click=lambda tid=tid: delete_task(tid)).props("flat color=negative").tooltip("Delete")

                def add_task():
                    title = (t_title.value or "").strip()
                    if not title:
                        task_message.text = "Task title is required."
                        return

                    try:
                        with connect() as con:
                            con.execute("""
                                INSERT INTO tasks (title, description, due_date, priority, status)
                                VALUES (?, ?, ?, ?, 'Pending')
                            """, (title, (t_desc.value or "").strip(), t_date.value, t_priority.value))

                        t_title.value = ""
                        t_desc.value = ""
                        task_message.text = ""
                        ui.notify("Task added successfully!", type="positive")
                        refresh_tasks()
                        refresh_overview()
                    except sqlite3.Error as e:
                        ui.notify(f"Error: {e}", type="negative")

                def mark_task_complete(tid):
                    with connect() as con:
                        con.execute("UPDATE tasks SET status = 'Completed' WHERE id = ?", (tid,))
                    ui.notify("Task marked as completed!", type="positive")
                    refresh_tasks()
                    refresh_overview()

                def mark_task_pending(tid):
                    with connect() as con:
                        con.execute("UPDATE tasks SET status = 'Pending' WHERE id = ?", (tid,))
                    ui.notify("Task marked as pending!", type="positive")
                    refresh_tasks()
                    refresh_overview()

                def delete_task(tid):
                    with connect() as con:
                        con.execute("DELETE FROM tasks WHERE id = ?", (tid,))
                    ui.notify("Task deleted successfully!", type="positive")
                    refresh_tasks()
                    refresh_overview()

    refresh_tasks()


# --------------------------------------------------
# START SERVER
# --------------------------------------------------

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8081)),
        title="NEXORA Business Management",
        storage_secret="NEXORA-CHANGE-THIS-TO-A-LONG-RANDOM-SECRET-2026",
        reload=False
    )
