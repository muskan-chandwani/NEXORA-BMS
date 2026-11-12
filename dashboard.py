import sqlite3
from pathlib import Path

from nicegui import ui
import auth

DB = Path(__file__).with_name("nexora.db")


def get_dashboard_data():
    with sqlite3.connect(DB, timeout=15) as con:
        customers = con.execute(
            "SELECT COUNT(*) FROM customers"
        ).fetchone()[0]

        orders = con.execute(
            "SELECT COUNT(*) FROM orders"
        ).fetchone()[0]

        totals = con.execute("""
            SELECT
                COALESCE(SUM(COALESCE(amount, 0)), 0),
                COALESCE(SUM(COALESCE(advance, 0)), 0)
            FROM orders
        """).fetchone()

        recent = con.execute("""
            SELECT id,
                   COALESCE(customer_name, customer, ''),
                   COALESCE(service, ''),
                   COALESCE(amount, 0),
                   COALESCE(status, '')
            FROM orders
            ORDER BY id DESC
            LIMIT 8
        """).fetchall()

    sales = float(totals[0] or 0)
    advance = float(totals[1] or 0)
    pending = sales - advance

    return customers, orders, sales, advance, pending, recent


@ui.page("/dashboard")
def dashboard_page():
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
        .nexora-card {
            background: #14213b;
            border: 1px solid #293c61;
            border-radius: 16px;
        }
    </style>
    """)

    with ui.column().classes("w-full p-4 md:p-8").style(
        "background:#080d1b;min-height:100vh"
    ):
        with ui.row().classes(
            "w-full items-center justify-between"
        ):
            with ui.column().classes("gap-0"):
                ui.label("◆ NEXORA").style(
                    "font-size:28px;font-weight:900;"
                    "letter-spacing:3px;color:white"
                )
                ui.label("BUSINESS CONTROL CENTER").style(
                    "color:#91a8d0;letter-spacing:2px;font-size:11px"
                )

            with ui.row().classes("items-center"):
                ui.label(f"Welcome, {user['name']}").style(
                    "color:#c6d4ed"
                )
                ui.button(
                    "Logout",
                    on_click=auth.logout
                ).props("color=negative outline")

        ui.separator().classes("my-4")

        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Business Overview").style(
                "font-size:25px;font-weight:800;color:white"
            )
            ui.button(
                "Refresh",
                icon="refresh",
                on_click=lambda: ui.navigate.to("/dashboard")
            ).props("outline color=primary")

        try:
            data = get_dashboard_data()
            customer_count, order_count, sales, advance, pending, recent = data
        except sqlite3.Error as error:
            ui.notify(f"Database error: {error}", type="negative")
            return

        cards = [
            ("Total Customers", customer_count, "groups", "#3988ff"),
            ("Total Orders", order_count, "shopping_bag", "#a879ff"),
            ("Total Sales", f"₹{sales:,.2f}", "payments", "#23c99a"),
            ("Total Advance", f"₹{advance:,.2f}", "account_balance_wallet", "#e5b84d"),
            ("Pending Balance", f"₹{pending:,.2f}", "pending_actions", "#ff7185"),
        ]

        with ui.grid(columns=2).classes("w-full gap-4"):
            for title, value, icon, accent in cards:
                with ui.card().classes("nexora-card w-full p-4"):
                    with ui.row().classes("items-center justify-between w-full"):
                        ui.label(title).style(
                            "color:#a9bbd8;font-size:13px"
                        )
                        ui.icon(icon).style(
                            f"font-size:25px;color:{accent}"
                        )
                    ui.label(str(value)).style(
                        f"font-size:25px;font-weight:900;color:{accent}"
                    )

        ui.label("Quick Actions").style(
            "font-size:22px;font-weight:800;color:white"
        ).classes("mt-6")

        with ui.grid(columns=2).classes("w-full gap-3"):
            ui.button(
                "Customer Management",
                icon="groups",
                on_click=lambda: ui.navigate.to("/")
            ).props("color=primary").classes("w-full")

            ui.button(
                "Order Management",
                icon="receipt_long",
                on_click=lambda: ui.navigate.to("/")
            ).props("color=secondary").classes("w-full")

        ui.label("Recent Orders").style(
            "font-size:22px;font-weight:800;color:white"
        ).classes("mt-6")

        if not recent:
            with ui.card().classes("nexora-card w-full"):
                ui.label("No orders added yet.").style(
                    "color:#a9bbd8"
                )
        else:
            with ui.card().classes("nexora-card w-full p-2"):
                for order_id, customer, service, amount, status in recent:
                    with ui.row().classes(
                        "w-full items-center justify-between p-2"
                    ):
                        with ui.column().classes("gap-0"):
                            ui.label(f"Order #{order_id}").style(
                                "color:#8eb5ff;font-weight:bold"
                            )
                            ui.label(customer or "Customer").style(
                                "color:white"
                            )
                            ui.label(service).style(
                                "color:#9aabc8;font-size:12px"
                            )
                        with ui.column().classes("items-end gap-0"):
                            ui.label(f"₹{float(amount or 0):,.2f}").style(
                                "color:#23c99a;font-weight:bold"
                            )
                            ui.label(status or "Pending").style(
                                "color:#a9bbd8;font-size:12px"
                            )
                    ui.separator()