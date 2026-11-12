import sqlite3
from pathlib import Path
from datetime import datetime
from nicegui import ui

DB = Path(__file__).with_name("nexora.db")


def connect():
    con = sqlite3.connect(DB, timeout=15)
    con.row_factory = sqlite3.Row
    return con


def setup_planner_database():
    with connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS planner_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                event_date TEXT,
                description TEXT,
                status TEXT DEFAULT 'Upcoming',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


def render_smart_planner():
    setup_planner_database()

    ui.label("Smart Planner & Event Hub").style("font-size:24px;font-weight:800;color:white")
    ui.label("Manage Delhi itineraries, weekly plans, important events, and deadline reminders.").style("color:#9eafca")

    # --- ADD NEW PLANNER ITEM FORM ---
    with ui.card().classes("n-card w-full p-4 mb-4"):
        ui.label("Add New Plan / Event").style("font-size:19px;font-weight:bold;color:white")
        
        p_category = ui.select(
            ["Delhi Planner", "Weekly Planner", "Important Event", "Deadline Reminder"],
            value="Important Event",
            label="Planner Category"
        ).props("outlined").classes("w-full")

        p_title = ui.label("").style("display:none") # Spacer/Placeholder if needed
        p_title_input = ui.input("Title / Topic").props("outlined").classes("w-full")
        p_desc = ui.textarea("Details / Description").props("outlined").classes("w-full")
        
        with ui.row().classes("w-full gap-3"):
            p_date = ui.input("Target Date / Deadline", value=datetime.now().strftime("%Y-%m-%d")).props("outlined").classes("flex-1")
            p_status = ui.select(["Upcoming", "In Progress", "Completed"], value="Upcoming", label="Status").props("outlined").classes("flex-1")

        planner_message = ui.label("").style("color:#ff8795")

        ui.button(
            "Save to Planner",
            icon="event_note",
            on_click=lambda: add_planner_item()
        ).props("color=primary").classes("mt-2")

    # --- FILTER BY CATEGORY ---
    with ui.row().classes("w-full items-center justify-between mb-2"):
        category_filter = ui.select(
            ["All", "Delhi Planner", "Weekly Planner", "Important Event", "Deadline Reminder"],
            value="All",
            label="Filter by Category"
        ).props("outlined").classes("w-60")

        planner_count_label = ui.label("").style("color:#e5b84d;font-weight:bold;font-size:14px;")

    planner_list = ui.column().classes("w-full gap-3")

    def refresh_planner():
        planner_list.clear()
        f_cat = category_filter.value or "All"

        with connect() as con:
            if f_cat == "All":
                rows = con.execute("SELECT * FROM planner_events ORDER BY id DESC").fetchall()
            else:
                rows = con.execute("SELECT * FROM planner_events WHERE category = ? ORDER BY id DESC", (f_cat,)).fetchall()

            total_items = con.execute("SELECT COUNT(*) FROM planner_events").fetchone()[0]

        planner_count_label.text = f"Total Items: {total_items}"

        with planner_list:
            if not rows:
                ui.label(f"No items found for '{f_cat}'.").style("color:#a9bbd8")
            
            for item in rows:
                iid = item["id"]
                cat = item["category"]
                status = item["status"]
                
                # Category color coding
                badge_color = "#3988ff"
                if cat == "Delhi Planner":
                    badge_color = "#a879ff"
                elif cat == "Weekly Planner":
                    badge_color = "#23c99a"
                elif cat == "Deadline Reminder":
                    badge_color = "#ff7185"

                with ui.card().classes("n-card w-full p-3").style(f"border-left: 6px solid {badge_color};"):
                    with ui.row().classes("w-full items-center justify-between"):
                        with ui.column().classes("gap-1"):
                            ui.row().classes("items-center gap-2")
                            ui.label(f"[{cat}] {item['title']}").style(
                                "font-size:17px;font-weight:bold;color:white;" + 
                                ("text-decoration: line-through; color: #888;" if status == "Completed" else "")
                            )
                            if item["description"]:
                                ui.label(item["description"]).style("color:#a9bbd8;font-size:13px")
                            
                            ui.label(f"Date/Deadline: {item['event_date']} | Status: {status}").style("color:#91a8d0;font-size:12px")

                        with ui.row().classes("items-center"):
                            if status != "Completed":
                                ui.button(
                                    icon="check",
                                    on_click=lambda iid=iid: mark_completed(iid)
                                ).props("flat color=positive").tooltip("Mark Completed")
                            else:
                                ui.button(
                                    icon="undo",
                                    on_click=lambda iid=iid: mark_upcoming(iid)
                                ).props("flat color=warning").tooltip("Mark Upcoming")
                            
                            ui.button(
                                icon="delete",
                                on_click=lambda iid=iid: delete_planner_item(iid)
                            ).props("flat color=negative").tooltip("Delete Item")

    def add_planner_item():
        title = (p_title_input.value or "").strip()
        if not title:
            planner_message.text = "Title is required."
            return

        try:
            with connect() as con:
                con.execute("""
                    INSERT INTO planner_events (category, title, event_date, description, status)
                    VALUES (?, ?, ?, ?, ?)
                """, (p_category.value, title, p_date.value, (p_desc.value or "").strip(), p_status.value))

            p_title_input.value = ""
            p_desc.value = ""
            planner_message.text = ""
            ui.notify("Plan added successfully!", type="positive")
            refresh_planner()
        except sqlite3.Error as e:
            ui.notify(f"Error: {e}", type="negative")

    def mark_completed(iid):
        with connect() as con:
            con.execute("UPDATE planner_events SET status = 'Completed' WHERE id = ?", (iid,))
        ui.notify("Marked as completed!", type="positive")
        refresh_planner()

    def mark_upcoming(iid):
        with connect() as con:
            con.execute("UPDATE planner_events SET status = 'Upcoming' WHERE id = ?", (iid,))
        ui.notify("Marked back to upcoming!", type="warning")
        refresh_planner()

    def delete_planner_item(iid):
        with connect() as con:
            con.execute("DELETE FROM planner_events WHERE id = ?", (iid,))
        ui.notify("Item deleted successfully!", type="positive")
        refresh_planner()

    category_filter.on_value_change(refresh_planner)
    refresh_planner()