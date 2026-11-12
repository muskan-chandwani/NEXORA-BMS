import sqlite3
from pathlib import Path
from nicegui import ui

DB = Path(__file__).with_name("nexora.db")

def connect():
    con = sqlite3.connect(DB, timeout=15)
    con.row_factory = sqlite3.Row
    return con

def setup_task_database():
    with connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                priority TEXT DEFAULT 'Medium',
                status TEXT DEFAULT 'Pending',
                due_date TEXT
            )
        """)

def render_task_manager():
    setup_task_database()

    ui.label("NEXORA Task Manager").style("font-size:24px;font-weight:800;color:white")
    ui.label("Manage your daily tasks, priorities, and deadlines efficiently.").style("color:#9eafca")

    # Form to add a new task
    with ui.row().classes("w-full gap-3 items-center n-card p-4 mb-4"):
        title_input = ui.input(placeholder="Task title or description...").props("outlined dark").classes("flex-1 bg-slate-800 text-white")
        priority_select = ui.select(["High", "Medium", "Low"], value="Medium", label="Priority").props("outlined dark").classes("w-32 bg-slate-800 text-white")
        due_input = ui.input(placeholder="Due Date (e.g., Tomorrow)").props("outlined dark").classes("w-40 bg-slate-800 text-white")

        def add_task():
            title = (title_input.value or "").strip()
            if not title:
                ui.notify("Please enter a task title!", color="negative")
                return
            
            with connect() as con:
                con.execute(
                    "INSERT INTO tasks (title, priority, status, due_date) VALUES (?, ?, 'Pending', ?)",
                    (title, priority_select.value, due_input.value or "Today")
                )
            title_input.value = ""
            due_input.value = ""
            ui.notify("Task added successfully!", color="positive")
            refresh_tasks()

        ui.button("Add Task", icon="add", on_click=add_task).props("color=primary").classes("h-12")

    # Container for task list
    task_container = ui.column().classes("w-full gap-3")

    def refresh_tasks():
        task_container.clear()
        with connect() as con:
            rows = con.execute("SELECT * FROM tasks ORDER BY id DESC").fetchall()

        with task_container:
            if not rows:
                with ui.card().classes("w-full p-4").style("background:#1e293b; color:#cbd5e1;"):
                    ui.label("No tasks found. Add your first task above!").style("font-size:14px;")
                return

            for row in rows:
                tid = row["id"]
                title = row["title"]
                priority = row["priority"]
                status = row["status"]
                due = row["due_date"]

                is_done = status == "Completed"
                bg_style = "background:#1e293b; opacity: 0.7;" if is_done else "background:#1e293b;"
                text_decoration = "line-through" if is_done else "none"

                with ui.card().classes("w-full p-4 flex-row items-center justify-between").style(bg_style):
                    with ui.row().classes("items-center gap-3"):
                        checkbox = ui.checkbox(value=is_done)
                        
                        def toggle_status(t_id=tid, cb=checkbox):
                            new_status = "Completed" if cb.value else "Pending"
                            with connect() as con:
                                con.execute("UPDATE tasks SET status = ? WHERE id = ?", (new_status, t_id))
                            refresh_tasks()

                        checkbox.on_value_change(toggle_status)

                        with ui.column().classes("gap-0"):
                            ui.label(title).style(f"font-size:16px; color:white; text-decoration:{text_decoration}; font-weight:600;")
                            ui.label(f"Priority: {priority} | Due: {due}").style("font-size:12px; color:#9eafca;")

                    def delete_task(t_id=tid):
                        with connect() as con:
                            con.execute("DELETE FROM tasks WHERE id = ?", (t_id,))
                        ui.notify("Task deleted", color="warning")
                        refresh_tasks()

                    ui.button(icon="delete", on_click=delete_task).props("flat color=red").classes("p-2")

    refresh_tasks()