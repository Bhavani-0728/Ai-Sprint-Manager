"""
ai_module.py
Rule-based sprint insights.
"""
from collections import Counter


def generate_insights(tasks, pending_threshold=5, workload_threshold=4, high_priority_threshold=3):
    # ADD THIS BELOW EXISTING CODE
    insights = []
    total = len(tasks or [])
    if total == 0:
        return ["No tasks available for AI insights."]

    pending = [t for t in tasks if t.get("status") in ("Todo", "Pending")]
    if len(pending) >= pending_threshold:
        insights.append(
            f"Too many pending tasks detected: {len(pending)} out of {total}. Consider re-prioritizing."
        )

    assignees = [t.get("assignee_name") or t.get("assigned_to") for t in tasks if (t.get("assignee_name") or t.get("assigned_to"))]
    if assignees:
        load = Counter(assignees)
        heavy = [(name, count) for name, count in load.items() if count >= workload_threshold]
        if heavy:
            details = ", ".join(f"{name} ({count})" for name, count in heavy)
            insights.append(f"High workload detected for: {details}. Consider balancing assignments.")

    high_priority = [t for t in tasks if t.get("priority") in ("High", "Critical") and t.get("status") != "Done"]
    if len(high_priority) >= high_priority_threshold:
        insights.append(
            f"High-priority overload: {len(high_priority)} High/Critical tasks are still not completed."
        )

    if not insights:
        insights.append("Sprint looks balanced. No major rule-based risks detected.")

    return insights
