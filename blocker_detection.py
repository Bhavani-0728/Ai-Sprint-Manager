"""
blocker_detection.py
Rule-based blocker detection for sprint tasks.
"""
from datetime import datetime, date


def _safe_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def detect_blockers(tasks, stale_days=3):
    # ADD THIS BELOW EXISTING CODE
    blockers = []
    warnings = []
    today = date.today()

    for task in tasks or []:
        title = task.get("title", "Untitled Task")
        status = task.get("status", "Todo")

        due_dt = _safe_date(task.get("due_date"))
        if due_dt and status != "Done" and due_dt < today:
            msg = f"Task '{title}' is overdue (due {due_dt})."
            blockers.append(msg)
            warnings.append(f"Overdue: {title}")

        if status == "In Progress":
            updated_dt = _safe_date(task.get("updated_at")) or _safe_date(task.get("created_at"))
            if updated_dt and (today - updated_dt).days >= stale_days:
                msg = f"Task '{title}' appears stuck in In Progress for {(today - updated_dt).days} day(s)."
                blockers.append(msg)
                warnings.append(f"Stuck In Progress: {title}")

    return blockers, warnings
