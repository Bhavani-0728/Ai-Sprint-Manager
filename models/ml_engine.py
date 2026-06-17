"""
models/ml_engine.py
AI/ML core: task completion time prediction, auto-blocker detection,
delay prediction, risk scoring, velocity forecasting, recommendations.
"""
import sqlite3
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
from datetime import datetime, date
import warnings
warnings.filterwarnings("ignore")

DB_PATH = "sprint_manager.db"

def _load_historical_tasks(conn):
    return pd.read_sql_query("""
        SELECT t.story_points, t.estimated_hours, t.actual_hours,
               t.priority, t.status, t.assignee_id,
               tm.velocity_avg, s.planned_points, s.completed_points
        FROM tasks t
        JOIN sprints s  ON t.sprint_id  = s.id
        JOIN team_members tm ON t.assignee_id = tm.id
        WHERE t.actual_hours IS NOT NULL AND s.status = 'Completed'
    """, conn)

def _encode_priority(p):
    return {"Low":1,"Medium":2,"High":3,"Critical":4}.get(p, 2)


# ── 1. Completion Time Predictor ──────────────────────────────────────────────
class CompletionTimePredictor:
    def __init__(self):
        self.model   = RandomForestRegressor(n_estimators=100, random_state=42)
        self.trained = False
        self.mae     = None

    def train(self, conn):
        df = _load_historical_tasks(conn)
        if len(df) < 5:
            return False
        return self.train_from_df(df)

    def train_from_df(self, df):
        if len(df) < 5:
            return False
        df = df.copy()
        # Remove invalid training rows
        df["actual_hours"] = pd.to_numeric(df["actual_hours"], errors="coerce")
        df = df.dropna(subset=["actual_hours"])

        if len(df) < 5:
            return False

        df["priority_enc"] = df["priority"].apply(_encode_priority)

        feats = [
            "story_points",
            "estimated_hours",
            "priority_enc",
            "velocity_avg",
            "planned_points"
        ]

        X = df[feats].apply(pd.to_numeric, errors="coerce")
        X = X.fillna(X.mean())

        y = df["actual_hours"]
        if len(X) >= 6:
            Xtr,Xte,ytr,yte = train_test_split(X, y, test_size=0.25, random_state=42)
            self.model.fit(Xtr, ytr)
            self.mae = round(mean_absolute_error(yte, self.model.predict(Xte)), 2)
        else:
            self.model.fit(X, y); self.mae = 0.0
        self.trained = True
        return True

    def predict(self, story_points, estimated_hours, priority, velocity_avg, planned_points):
        if not self.trained:
            ratio = {"Low":0.9,"Medium":1.0,"High":1.15,"Critical":1.25}.get(priority, 1.0)
            return round(estimated_hours * ratio, 1)
        X = np.array([[story_points, estimated_hours, _encode_priority(priority),
                       velocity_avg, planned_points]])
        return round(float(self.model.predict(X)[0]), 1)

    def feature_importances(self):
        if not self.trained: return {}
        names = ["Story Points","Estimated Hours","Priority","Member Velocity","Sprint Capacity"]
        return dict(zip(names, np.round(self.model.feature_importances_, 3)))


# ── 2. AUTO Blocker & Delay Detector ─────────────────────────────────────────
class AutoBlockerDetector:
    """
    Automatically detects blockers and delays WITHOUT any manual user input.
    Analyses task age, hour overruns, sprint deadlines, stagnation.
    """

    def detect(self, task: dict, sprint: dict, sprint_remaining_days: int) -> dict:
        """
        Returns:
          auto_blocked  : bool   — system believes this task is effectively blocked
          delay_risk    : str    — 'none' | 'at_risk' | 'delayed'
          delay_days    : int    — estimated days of delay
          reasons       : list   — human-readable reasons
          suggestions   : list   — AI action suggestions
        """
        reasons     = []
        suggestions = []
        auto_blocked = False
        delay_days   = 0

        status       = task.get("status", "Todo")
        priority     = task.get("priority", "Medium")
        story_points = task.get("story_points", 1)
        est_hours    = task.get("estimated_hours") or (story_points * 2)
        act_hours    = task.get("actual_hours") or 0.0
        updated_at   = task.get("updated_at", "")
        created_at   = task.get("created_at", "")
        sprint_end   = sprint.get("end_date", "")
        velocity     = task.get("velocity_avg") or 12.0

        today = date.today()

        # ── Rule 1: Stagnation — In Progress but not updated in 2+ days ────────
        if status == "In Progress" and updated_at:
            try:
                last_update = datetime.strptime(str(updated_at)[:10], "%Y-%m-%d").date()
                stale_days  = (today - last_update).days
                if stale_days >= 3:
                    auto_blocked = True
                    delay_days  += stale_days
                    reasons.append(f"🕐 In Progress for {stale_days} days with no update — likely stalled")
                    suggestions.append("Request a status update in daily standup immediately")
                elif stale_days >= 2:
                    reasons.append(f"⚠️ No progress logged in {stale_days} days")
                    suggestions.append("Check in with assignee on blockers")
            except: pass

        # ── Rule 2: Hours overrun — actual > 130% of estimate ──────────────────
        if act_hours and est_hours and act_hours > est_hours * 1.3:
            overrun_pct = round((act_hours - est_hours) / est_hours * 100)
            auto_blocked = True
            delay_days  += int((act_hours - est_hours) / 8)
            reasons.append(f"📊 Actual hours ({act_hours}h) exceed estimate ({est_hours}h) by {overrun_pct}%")
            suggestions.append("Re-estimate task and consider splitting into subtasks")

        # ── Rule 3: Not started + sprint deadline near ──────────────────────────
        if status == "Todo" and sprint_remaining_days <= 3:
            auto_blocked = True
            delay_days  += max(0, int(est_hours / 8) - sprint_remaining_days)
            reasons.append(f"⏰ Task not started with only {sprint_remaining_days} day(s) left in sprint")
            suggestions.append("Descope to next sprint or assign immediately")

        # ── Rule 4: High/Critical + Todo + past halfway point ──────────────────
        if status == "Todo" and priority in ("Critical","High"):
            sprint_start = sprint.get("start_date","")
            sprint_end_d = sprint.get("end_date","")
            try:
                s_start = datetime.strptime(str(sprint_start)[:10], "%Y-%m-%d").date()
                s_end   = datetime.strptime(str(sprint_end_d)[:10], "%Y-%m-%d").date()
                total_days   = max((s_end - s_start).days, 1)
                elapsed_days = (today - s_start).days
                if elapsed_days > total_days * 0.6:
                    auto_blocked = True
                    reasons.append(f"🚨 {priority} task still unstarted at {int(elapsed_days/total_days*100)}% of sprint")
                    suggestions.append("Assign immediately or escalate to Scrum Master")
            except: pass

        # ── Rule 5: Estimated hours > remaining sprint capacity ─────────────────
        if sprint_remaining_days > 0 and est_hours:
            remaining_capacity = sprint_remaining_days * 8 * 0.7  # 70% utilisation
            if est_hours > remaining_capacity and status != "Done":
                delay_days = max(delay_days, int((est_hours - remaining_capacity) / 8) + 1)
                reasons.append(f"📅 Needs ~{est_hours}h but only ~{remaining_capacity:.0f}h capacity left")
                suggestions.append("Consider partial completion or sprint extension")

        # ── Rule 6: Velocity mismatch ───────────────────────────────────────────
        if story_points > velocity * 0.8 and status != "Done":
            reasons.append(f"⚡ Task ({story_points}pt) may exceed assignee's typical capacity ({velocity:.0f}pt avg)")
            suggestions.append("Pair with another team member or break down the task")

        # Determine delay risk
        if auto_blocked or delay_days >= 2:
            delay_risk = "delayed"
        elif len(reasons) >= 2 or delay_days >= 1:
            delay_risk = "at_risk"
        else:
            delay_risk = "none"

        return {
            "auto_blocked": auto_blocked,
            "delay_risk":   delay_risk,
            "delay_days":   delay_days,
            "reasons":      reasons,
            "suggestions":  suggestions,
        }

    def scan_sprint(self, tasks: list, sprint: dict) -> dict:
        """Scan all tasks in a sprint and return summary."""
        sprint_end = sprint.get("end_date","")
        today = date.today()
        try:
            s_end = datetime.strptime(str(sprint_end)[:10], "%Y-%m-%d").date()
            remaining_days = max((s_end - today).days, 0)
        except:
            remaining_days = 7

        results = []
        auto_blocked_count = 0
        delayed_count      = 0
        at_risk_count      = 0

        for t in tasks:
            if t.get("status") == "Done":
                results.append({**t, "auto_detection": {"auto_blocked":False,"delay_risk":"none","delay_days":0,"reasons":[],"suggestions":[]}})
                continue
            det = self.detect(t, sprint, remaining_days)
            results.append({**t, "auto_detection": det})
            if det["auto_blocked"]:     auto_blocked_count += 1
            if det["delay_risk"] == "delayed":  delayed_count  += 1
            elif det["delay_risk"] == "at_risk": at_risk_count += 1

        return {
            "tasks":               results,
            "remaining_days":      remaining_days,
            "auto_blocked_count":  auto_blocked_count,
            "delayed_count":       delayed_count,
            "at_risk_count":       at_risk_count,
            "total_delay_days":    sum(t["auto_detection"]["delay_days"] for t in results),
        }


# ── 3. Risk Detector (manual + rule-based) ────────────────────────────────────
class RiskDetector:
    def assess_task_risk(self, task, member_velocity, sprint_remaining_days):
        score = 0; reasons = []
        if task.get("actual_hours") is None and task.get("estimated_hours"):
            if task["estimated_hours"]/8 > sprint_remaining_days:
                score += 3; reasons.append(f"Estimated {task['estimated_hours']}h but {sprint_remaining_days} days left")
        if task.get("priority") in ("Critical","High") and task.get("status") == "Todo":
            score += 2; reasons.append(f"{task['priority']} priority not yet started")
        if task.get("status") == "Blocked":
            score += 4; reasons.append("Task is manually marked as blocked")
        if task.get("story_points",1) > member_velocity * 0.7:
            score += 2; reasons.append(f"Large task relative to velocity")
        if not task.get("assignee_id"):
            score += 2; reasons.append("No assignee")
        level = "low" if score<=2 else "medium" if score<=5 else "high"
        return {"level":level, "score":score, "reasons":reasons}

    def assess_sprint_risk(self, sprint, tasks):
        total = len(tasks)
        if total == 0: return {"level":"low","score":0,"reasons":["No tasks"]}
        done    = sum(1 for t in tasks if t["status"]=="Done")
        blocked = sum(1 for t in tasks if t["status"]=="Blocked")
        hi_undo = sum(1 for t in tasks if t["priority"] in ("Critical","High") and t["status"]!="Done")
        pp = sprint.get("planned_points",40); cp = sprint.get("completed_points",0)
        score = 0; reasons = []
        if pp>0 and (pp-cp) > pp*0.3:
            score+=3; reasons.append(f"Completion gap: {pp-cp} pts behind ({done}/{total} tasks done)")
        if blocked>0:
            score+=blocked*2; reasons.append(f"{blocked} manually blocked task(s)")
        if hi_undo>2:
            score+=2; reasons.append(f"{hi_undo} critical/high tasks incomplete")
        level = "low" if score<=2 else "medium" if score<=6 else "high"
        return {"level":level,"score":score,"reasons":reasons}


# ── 4. Velocity Forecaster ────────────────────────────────────────────────────
class VelocityForecaster:
    def forecast(self, velocities):
        if not velocities: return {"forecast":30,"trend":"stable","confidence":0.5}
        v = np.array(velocities, dtype=float); n = len(v)
        w = np.arange(1, n+1, dtype=float)
        wma = float(np.dot(w,v)/w.sum())
        trend = "improving" if n>=2 and v[-1]-v[-2]>1 else "declining" if n>=2 and v[-1]-v[-2]<-1 else "stable"
        std   = float(np.std(v))
        conf  = max(0.4, 1.0 - std/(wma+1e-9))
        return {"forecast":round(wma,1),"trend":trend,"confidence":round(conf,2),
                "historical":list(velocities),"std":round(std,2)}


# ── 5. Recommendation Engine ──────────────────────────────────────────────────
class RecommendationEngine:
    def generate(self, sprint_risk, tasks, velocity_forecast, team_members):
        recs = []
        if sprint_risk["level"]=="high":
            recs.append({"type":"warning","icon":"🚨","title":"Sprint at High Risk",
                          "body":"Consider descoping low-priority tasks. "+"; ".join(sprint_risk["reasons"][:2])})
        elif sprint_risk["level"]=="medium":
            recs.append({"type":"caution","icon":"⚠️","title":"Monitor Sprint Progress",
                          "body":"Sprint shows moderate risk. " + (sprint_risk["reasons"][0] if sprint_risk["reasons"] else "")})
        blocked = [t for t in tasks if t.get("status")=="Blocked"]
        if blocked:
            recs.append({"type":"action","icon":"🔓","title":f"Resolve {len(blocked)} Manual Blocker(s)",
                          "body":f"Blocked: {', '.join(t['title'] for t in blocked[:2])}. Escalate immediately."})
        if velocity_forecast.get("trend")=="declining":
            recs.append({"type":"info","icon":"📉","title":"Velocity Declining",
                          "body":f"Team velocity trending down. Run a retrospective. Forecast: {velocity_forecast['forecast']} pts."})
        elif velocity_forecast.get("trend")=="improving":
            recs.append({"type":"success","icon":"📈","title":"Velocity Improving",
                          "body":f"Great momentum! Next sprint forecast: {velocity_forecast['forecast']} pts."})
        if team_members:
            tc = pd.Series([t.get("assignee_id") for t in tasks if t.get("assignee_id")]).value_counts()
            if len(tc)>1 and tc.max()>tc.min()*2:
                recs.append({"type":"info","icon":"⚖️","title":"Uneven Workload",
                              "body":"Some members have significantly more tasks. Rebalance to prevent burnout."})
        if not recs:
            recs.append({"type":"success","icon":"✅","title":"Sprint Looks Healthy",
                          "body":"No major risks detected. Keep up the good work!"})
        return recs


# ── 6. Sprint Health Score ────────────────────────────────────────────────────
def compute_sprint_health(tasks, sprint):
    if not tasks: return {"score":50,"grade":"C","breakdown":{},"details":{}}
    total   = len(tasks)
    done    = sum(1 for t in tasks if t["status"]=="Done")
    blocked = sum(1 for t in tasks if t["status"]=="Blocked")
    crit_d  = sum(1 for t in tasks if t["priority"]=="Critical" and t["status"]=="Done")
    crit_t  = sum(1 for t in tasks if t["priority"]=="Critical")
    cp = sprint.get("completed_points",0); pp = sprint.get("planned_points",1)
    c1 = (done/total)*40
    c2 = max(0, 20-(blocked*7))
    c3 = min(25, (cp/max(pp,1))*25)
    c4 = (crit_d/max(crit_t,1))*15
    total_score = max(0, min(100, int(c1+c2+c3+c4)))
    grade = "A" if total_score>=85 else "B" if total_score>=70 else "C" if total_score>=55 else "D" if total_score>=40 else "F"
    return {"score":total_score,"grade":grade,
            "breakdown":{"Completion Rate":round(c1,1),"No Blockers":round(c2,1),
                          "Velocity Match":round(c3,1),"Critical Tasks":round(c4,1)},
            "details":{"done":done,"blocked":blocked,"total":total}}