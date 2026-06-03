"""
app.py — AI-Powered Agile Sprint Manager (Jira-style)
CVR College of Engineering | IOMP Batch 19
Run: streamlit run app.py
"""
import streamlit as st
import sqlite3, pandas as pd, numpy as np, sys, os, io
from datetime import date, timedelta, datetime
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(__file__))
from data.db_setup import create_tables, seed_data, get_conn, log_activity
from auth import signup_user, login_user, logout_user
from ai_module import generate_insights
from blocker_detection import detect_blockers
from models.ml_engine import (
    CompletionTimePredictor, RiskDetector, AutoBlockerDetector,
    VelocityForecaster, RecommendationEngine, compute_sprint_health
)

st.set_page_config(page_title="SprintAI", page_icon="⚡",
                   layout="wide", initial_sidebar_state="expanded")

# ── session state for active tab ──────────────────────────────────────────────
if "tab" not in st.session_state:
    st.session_state.tab = "Summary"
# ADD THIS BELOW EXISTING CODE
if "user" not in st.session_state:
    st.session_state["user"] = None
if "role" not in st.session_state:
    st.session_state["role"] = None


def render_auth_gate():
    # ADD THIS BELOW EXISTING CODE
    # Center auth vertically only on this screen (do not use orphan HTML divs — Streamlit
    # renders each st.markdown as a sibling, so never split a decorative wrapper across multiple calls.)
    st.markdown(
        """
        <style>
        section.main > div.block-container {
            min-height: calc(100vh - 100px) !important;
            display: flex !important;
            flex-direction: column !important;
            justify-content: center !important;
            padding-top: 24px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    left, mid, right = st.columns([1, 1.15, 1])
    with mid:
        st.markdown(
            '<div class="auth-brand">'
            '<div class="auth-title-center">⚡ SprintAI</div>'
            '<div class="auth-sub-center">Login / Signup to continue</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        ltab, stab = st.tabs(["Login", "Signup"])

        with ltab:
            with st.form("login_form"):
                lu = st.text_input("Email", placeholder="name@company.com")
                lp = st.text_input("Password", type="password", placeholder="Enter your password")
                if st.form_submit_button("Login", type="primary", use_container_width=True):
                    ok, msg = login_user(lu, lp)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    st.error(msg)

        with stab:
            with st.form("signup_form"):
                su = st.text_input("Email", placeholder="name@company.com")
                sp = st.text_input("Create Password", type="password", placeholder="Minimum 8 characters")
                sr = st.selectbox("Role", ["Member", "Manager"])
                if st.form_submit_button("Create Account", type="primary", use_container_width=True):
                    ok, msg = signup_user(su, sp, sr)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap');
html,body,[class*="css"]  { font-family:'Inter',sans-serif; }
code,.stCode              { font-family:'DM Mono',monospace !important; }
.main                     { background:#0d1117; }
.block-container          { padding:68px 0 32px 0 !important; max-width:100% !important; }
section[data-testid="stSidebar"] { background:#161b22; border-right:1px solid #30363d; }
section[data-testid="stSidebar"] .block-container { padding:16px !important; }

/* hide only deploy button, keep sidebar toggle visible */
#MainMenu { visibility:hidden; }
footer    { visibility:hidden; }

/* headings & text */
h1,h2,h3              { color:#e6edf3 !important; }
p,li,.stMarkdown      { color:#8b949e; font-size:13px; }
label                 { color:#8b949e !important; font-size:12px !important; }
hr                    { border-color:#21262d !important; margin:10px 0 !important; }

/* inputs */
.stTextInput>div>div>input,
.stTextArea>div>div>textarea,
.stNumberInput input,
.stSelectbox>div>div  { background:#21262d !important; border:1px solid #30363d !important;
                         color:#e6edf3 !important; border-radius:6px !important; font-size:13px !important; }
.stDateInput input    { background:#21262d !important; color:#e6edf3 !important; border-radius:6px !important; }
.stMultiSelect>div    { background:#21262d !important; border:1px solid #30363d !important; border-radius:6px !important; }

/* buttons */
.stButton>button      { border-radius:6px !important; font-weight:500 !important;
                         font-size:12px !important; border:none !important; }
.stButton>button[kind="primary"]   { background:#238636 !important; color:#fff !important; }
.stButton>button[kind="secondary"] { background:#21262d !important; color:#c9d1d9 !important; border:1px solid #30363d !important; }

/* form */
.stForm               { background:#161b22 !important; border:1px solid #30363d !important;
                         border-radius:8px !important; padding:16px !important; }

/* metric */
[data-testid="stMetricValue"] { color:#e6edf3 !important; font-weight:700 !important; font-size:1.4rem !important; }
[data-testid="stMetricLabel"] { color:#8b949e !important; font-size:11px !important; text-transform:uppercase; letter-spacing:.5px; }

/* dataframe */
.stDataFrame          { border-radius:8px; overflow:hidden; border:1px solid #30363d !important; }

/* expander */
.streamlit-expanderHeader   { background:#161b22 !important; border-radius:6px !important; border:1px solid #30363d !important; }
.streamlit-expanderContent  { background:#0d1117 !important; border:1px solid #30363d !important; border-top:none !important; }

/* ── TOP NAV BAR ── */
.top-nav              { background:#161b22; border-bottom:1px solid #30363d;
                         padding:0; display:flex; align-items:stretch; width:100%; }
.top-nav-logo         { display:flex; align-items:center; gap:8px; padding:0 20px;
                         border-right:1px solid #30363d; min-width:200px; }
.proj-badge           { width:28px; height:28px; border-radius:6px;
                         background:linear-gradient(135deg,#f97316,#ef4444);
                         display:flex; align-items:center; justify-content:center; font-size:14px; }
.proj-name            { color:#e6edf3; font-weight:700; font-size:14px; }

/* TAB BUTTONS — these override Streamlit button styling */
div[data-testid="column"] .stButton>button.tab-btn {
    background: transparent !important;
    color: #8b949e !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    border-radius: 0 !important;
    padding: 14px 14px 12px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    height: auto !important;
    width: 100% !important;
}

/* Page content */
.page-wrap            { padding:20px 24px; }

/* cards */
.card                 { background:#161b22; border:1px solid #30363d; border-radius:8px; padding:16px 18px; margin-bottom:12px; }
.sum-num              { font-size:28px; font-weight:700; }
.sum-lbl              { font-size:11px; color:#8b949e; text-transform:uppercase; letter-spacing:.5px; margin-top:2px; }

/* rec cards */
.rc                   { border-radius:8px; padding:11px 14px; margin-bottom:8px; font-size:13px; line-height:1.5; }
.rc-warn              { background:#1a0e0e; border-left:3px solid #f85149; }
.rc-caut              { background:#1a1500; border-left:3px solid #d29922; }
.rc-act               { background:#0d1f33; border-left:3px solid #58a6ff; }
.rc-info              { background:#13111f; border-left:3px solid #a78bfa; }
.rc-ok                { background:#0a1f12; border-left:3px solid #3fb950; }

/* auto-detect alert */
.auto-blk             { background:#1a0b0b; border:1px solid #f8514940; border-radius:8px; padding:12px 14px; margin-bottom:8px; }
.auto-risk            { background:#1a1200; border:1px solid #d2992240; border-radius:8px; padding:12px 14px; margin-bottom:8px; }

/* badges */
.badge                { display:inline-block; padding:2px 8px; border-radius:12px; font-size:11px; font-weight:600; }
.p-crit               { background:#3d1a1a; color:#ff6b6b; border:1px solid #ff6b6b40; }
.p-high               { background:#3d2e0a; color:#fbbf24; border:1px solid #fbbf2440; }
.p-med                { background:#0d2239; color:#60a5fa; border:1px solid #60a5fa40; }
.p-low                { background:#1a2039; color:#818cf8; border:1px solid #818cf840; }
.s-done               { background:#0a2a18; color:#3fb950; border:1px solid #3fb95040; }
.s-prog               { background:#0d2239; color:#58a6ff; border:1px solid #58a6ff40; }
.s-todo               { background:#21262d; color:#8b949e; border:1px solid #30363d; }
.s-blk                { background:#3d1a1a; color:#ff6b6b; border:1px solid #ff6b6b40; }
.s-auto               { background:#3d1a3d; color:#e879f9; border:1px solid #e879f940; }

/* activity */
.act-row              { display:flex; gap:10px; padding:9px 0; border-bottom:1px solid #21262d; align-items:flex-start; }

/* auth page */
.auth-brand            { margin-bottom:18px; }
.auth-title-center    { color:#e6edf3; font-size:30px; font-weight:700; text-align:center; margin-bottom:10px; letter-spacing:-.4px; }
.auth-sub-center      { color:#8b949e; font-size:13px; text-align:center; margin-bottom:0; }
</style>
""", unsafe_allow_html=True)

# ── DB & ML init ──────────────────────────────────────────────────────────────
# ADD THIS BELOW EXISTING CODE
_c = get_conn()
create_tables(_c)
seed_data(_c)  # fills demo project when DB is new (skipped if projects already exist)
_c.close()

# ADD THIS BELOW EXISTING CODE
if not st.session_state.get("user"):
    render_auth_gate()
    st.stop()

@st.cache_resource
def get_base_models():
    return RiskDetector(), AutoBlockerDetector(), VelocityForecaster(), RecommendationEngine()

def get_predictor_for_project(project_id):
    """Train a fresh predictor only on this project's historical tasks."""
    p = CompletionTimePredictor()
    conn = get_conn()
    df = pd.read_sql_query("""
        SELECT t.story_points, t.estimated_hours, t.actual_hours,
               t.priority, tm.velocity_avg, s.planned_points, s.completed_points
        FROM tasks t
        JOIN sprints s ON t.sprint_id = s.id
        JOIN team_members tm ON t.assignee_id = tm.id
        WHERE t.actual_hours IS NOT NULL
          AND s.status = 'Completed'
          AND s.project_id = ?
    """, conn, params=[project_id])
    conn.close()
    count = len(df)
    if count >= 5:
        p.train_from_df(df)
    return p, count

risk_det, auto_det, vel_fc, rec_eng = get_base_models()

# ── DB helpers ────────────────────────────────────────────────────────────────
def qry(sql, params=()):
    c=get_conn(); df=pd.read_sql_query(sql,c,params=list(params)); c.close(); return df

def exe(sql, params=()):
    c=get_conn(); cur=c.execute(sql,list(params)); c.commit(); lid=cur.lastrowid; c.close(); return lid

def load_projects():   return qry("SELECT * FROM projects ORDER BY id")
def load_sprints(pid=None, status=None):
    s="SELECT * FROM sprints WHERE 1=1"; p=[]
    if pid:    s+=" AND project_id=?"; p.append(pid)
    if status: s+=" AND status=?";     p.append(status)
    return qry(s+" ORDER BY id", p)
def load_active(pid):
    df=qry("SELECT * FROM sprints WHERE status='Active' AND project_id=? ORDER BY id DESC LIMIT 1",[pid])
    return df.iloc[0].to_dict() if not df.empty else None

def apply_role_task_filter(df):
    # ADD THIS BELOW EXISTING CODE
    if df is None or df.empty:
        return df
    role = st.session_state.get("role")
    user = st.session_state.get("user")
    user_name = st.session_state.get("user_name")
    if role == "Member" and user:
        # Match by explicit full name first, then fallback to email local-part heuristic.
        if "assignee_name" in df.columns:
            if user_name:
                exact = df[df["assignee_name"] == user_name]
                if not exact.empty:
                    return exact
            local = str(user).split("@")[0].lower().replace(".", "").replace("_", "")
            return df[
                df["assignee_name"].fillna("").str.lower().str.replace(r"[^a-z0-9]", "", regex=True).str.contains(local)
            ]
        if "assigned_to" in df.columns:
            return df[df["assigned_to"] == user]
    return df

def load_tasks(sprint_id=None, project_id=None, include_planning=False):
    s="""SELECT t.*,tm.name as assignee_name,tm.velocity_avg,tm.avatar_color,sp.status as sprint_status
         FROM tasks t
         LEFT JOIN team_members tm ON t.assignee_id=tm.id
         LEFT JOIN sprints sp ON t.sprint_id=sp.id
         WHERE 1=1"""
    p=[]
    if sprint_id:  s+=" AND t.sprint_id=?";  p.append(sprint_id)
    if project_id: s+=" AND t.project_id=?"; p.append(project_id)
    # Hide tasks from not-started sprints unless explicitly requested.
    if not include_planning:
        s+=" AND (t.sprint_id IS NULL OR sp.status IS NULL OR sp.status!='Planning')"
    tdf = qry(s,p)
    return apply_role_task_filter(tdf)
def load_team(pid):     return qry("SELECT * FROM team_members WHERE project_id=? ORDER BY id",[pid])
def load_metrics(pid):  return qry("""SELECT sm.*,s.name as sprint_name,s.planned_points
    FROM sprint_metrics sm JOIN sprints s ON sm.sprint_id=s.id
    WHERE s.project_id=? ORDER BY sm.sprint_id""",[pid])
def load_activity(pid, n=20): return qry("SELECT * FROM activity_log WHERE project_id=? ORDER BY id DESC LIMIT ?",[pid,n])

def reconcile_sprint_points(pid):
    # ADD THIS BELOW EXISTING CODE
    # Keep sprint point counters aligned with actual tasks in DB.
    c = get_conn()
    c.execute("""
        UPDATE sprints
        SET planned_points = COALESCE((
            SELECT SUM(t.story_points) FROM tasks t WHERE t.sprint_id = sprints.id
        ), 0),
        completed_points = COALESCE((
            SELECT SUM(t.story_points) FROM tasks t WHERE t.sprint_id = sprints.id AND t.status='Done'
        ), 0)
        WHERE project_id = ?
    """, [pid])
    c.commit()
    c.close()

def member_opts(tdf):
    d={None:"— Unassigned —"}
    d.update({r["id"]:f"{r['name']} ({r['role']})" for _,r in tdf.iterrows()})
    return d

def pbadge(p):
    m={"Critical":"p-crit","High":"p-high","Medium":"p-med","Low":"p-low"}
    i={"Critical":"🔴","High":"🟡","Medium":"🔵","Low":"⚪"}
    return f'<span class="badge {m.get(p,"p-med")}">{i.get(p,"")} {p}</span>'

def sbadge(s, auto=False):
    if auto: return '<span class="badge s-auto">🤖 Auto-Flagged</span>'
    m={"Done":"s-done","In Progress":"s-prog","Todo":"s-todo","Blocked":"s-blk"}
    i={"Done":"●","In Progress":"◑","Todo":"○","Blocked":"✕"}
    return f'<span class="badge {m.get(s,"s-todo")}">{i.get(s,"")} {s}</span>'

def av_html(name, color="#3b82f6", size=26):
    return (f'<div style="width:{size}px;height:{size}px;border-radius:50%;background:{color};'
            f'display:inline-flex;align-items:center;justify-content:center;'
            f'font-size:{int(size*.4)}px;font-weight:700;color:#fff;flex-shrink:0">{name[0].upper()}</div>')

def chart_buf(fig):
    buf=io.BytesIO(); plt.savefig(buf,format='png',bbox_inches='tight',transparent=True,dpi=120)
    buf.seek(0); plt.close(fig); return buf

# ── SIDEBAR — project only, no nav ───────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding:12px 2px 14px">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
        <div style="width:40px;height:40px;border-radius:10px;flex-shrink:0;
             background:linear-gradient(135deg,#2563eb,#7c3aed);
             box-shadow:0 0 18px #2563eb55;
             display:flex;align-items:center;justify-content:center;font-size:22px">⚡</div>
        <div>
          <div style="color:#e6edf3;font-weight:700;font-size:17px;letter-spacing:-.3px">SprintAI</div>
          <div style="color:#8b949e;font-size:10px;letter-spacing:.3px"></div>
        </div>
      </div>
      <div style="background:linear-gradient(90deg,#2563eb18,#7c3aed18);
           border:1px solid #2563eb30;border-radius:6px;
           padding:5px 10px;font-size:11px;color:#8b949e;text-align:center;letter-spacing:.2px">
        🤖 AI-Powered Agile Manager
      </div>
    </div>""", unsafe_allow_html=True)
    st.divider()

    projects = load_projects()
    if not projects.empty:
        sel_p    = st.selectbox("📁 Project", projects["name"].tolist(), label_visibility="visible")
        prow     = projects[projects["name"]==sel_p].iloc[0]
        proj_id  = int(prow["id"]); proj_name = prow["name"]
    else:
        proj_id = None; proj_name = "—"

    # ADD THIS BELOW EXISTING CODE
    if st.session_state.get("role") == "Manager":
        with st.expander("＋ New Project"):
            with st.form("np"):
                n=st.text_input("Name *"); d=st.text_area("Description",height=50)
                if st.form_submit_button("Create",type="primary"):
                    if n.strip(): exe("INSERT INTO projects(name,description)VALUES(?,?)",(n.strip(),d)); st.rerun()
                    else: st.error("Name required")
    else:
        st.caption("Member access: project creation is restricted.")

    if proj_id:
        st.divider()
        act_s = load_active(proj_id)
        if act_s:
            pp=act_s["planned_points"]; cp=act_s["completed_points"]; pct=cp/max(pp,1)
            st.markdown(f'<div style="color:#3fb950;font-size:12px;font-weight:600;margin-bottom:4px">🟢 {act_s["name"]}</div>', unsafe_allow_html=True)
            st.caption(act_s.get("goal","") or "No goal set")
            st.progress(min(pct,1.0), text=f"{cp}/{pp} pts · {pct*100:.0f}%")
            # Auto-detection summary in sidebar
            tdf_s = load_tasks(sprint_id=act_s["id"])
            if not tdf_s.empty:
                scan = auto_det.scan_sprint(tdf_s.to_dict("records"), act_s)
                if scan["auto_blocked_count"] or scan["delayed_count"] or scan["at_risk_count"]:
                    st.markdown(f"""
                    <div style="background:#1a0b0b;border:1px solid #f8514940;border-radius:6px;padding:8px 10px;margin-top:8px">
                      <div style="color:#f85149;font-size:11px;font-weight:700">🤖 AI DETECTED</div>
                      <div style="color:#c9d1d9;font-size:11px;margin-top:4px">
                        {f'⛔ {scan["auto_blocked_count"]} auto-flagged' if scan["auto_blocked_count"] else ''}
                        {f'<br>⏰ {scan["delayed_count"]} delayed' if scan["delayed_count"] else ''}
                        {f'<br>⚠️ {scan["at_risk_count"]} at risk' if scan["at_risk_count"] else ''}
                      </div>
                    </div>""", unsafe_allow_html=True)
        else:
            st.caption("⚪ No active sprint")

    st.divider()
    st.caption("Python · Streamlit · Scikit-learn · SQLite")
    # ADD THIS BELOW EXISTING CODE
    st.caption(f"👤 {st.session_state.get('user')} ({st.session_state.get('role')})")
    if st.button("🚪 Logout", use_container_width=True):
        logout_user()
        st.rerun()

# ── Guard ─────────────────────────────────────────────────────────────────────
if not proj_id:
    st.markdown("""
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:70vh;gap:12px">
      <div style="font-size:48px">⚡</div>
      <div style="color:#e6edf3;font-size:22px;font-weight:700">Welcome to SprintAI</div>
      <div style="color:#8b949e">Create your first project in the sidebar.</div>
    </div>""", unsafe_allow_html=True)
    st.stop()

# ADD THIS BELOW EXISTING CODE
reconcile_sprint_points(proj_id)

# ══════════════════════════════════════════════════════════════════════════════
#  TOP NAV — project header + clickable tabs
# ══════════════════════════════════════════════════════════════════════════════
TABS = ["Summary","List","Board","Sprints","Task Creation","Team","AI Insights","Reports"]
TAB_ICONS = {"Summary":"📊","List":"📋","Board":"🗂️","Sprints":"🏃",
             "Task Creation":"🗒️","Team":"👥","AI Insights":"🔮","Reports":"📄"}

# ── Project name above tabs (like Jira) ──────────────────────────────────────
st.markdown(f"""
<div style="background:#161b22;padding:8px 24px 0 24px;border-bottom:none">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">
    <div style="width:28px;height:28px;border-radius:6px;
         background:linear-gradient(135deg,#f97316,#ef4444);
         display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0">🚀</div>
    <span style="color:#e6edf3;font-size:20px;font-weight:700">{proj_name}</span>
  </div>
</div>""", unsafe_allow_html=True)

# Tab bar — using columns + buttons
tab_cols = st.columns(len(TABS))
for i, t in enumerate(TABS):
    with tab_cols[i]:
        is_active = (st.session_state.tab == t)
        label = f"{TAB_ICONS[t]} {t}"
        if is_active:
            st.markdown(f"""
            <div style="text-align:center;padding:10px 4px 8px;
                 border-bottom:2px solid #58a6ff;background:#161b22;
                 color:#58a6ff;font-size:12px;font-weight:600;
                 cursor:pointer;white-space:nowrap">{label}</div>""",
                unsafe_allow_html=True)
        else:
            if st.button(label, key=f"tab_{t}", use_container_width=True):
                st.session_state.tab = t
                st.rerun()

st.markdown('<div style="background:#30363d;height:1px;margin-bottom:0"></div>', unsafe_allow_html=True)

page = st.session_state.tab

# ══════════════════════════════════════════════════════════════════════════════
#  📊 SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
if page == "Summary":
    st.markdown('<div class="page-wrap">', unsafe_allow_html=True)

    act   = load_active(proj_id)
    tdf   = load_tasks(sprint_id=act["id"]) if act else load_tasks(project_id=proj_id)
    tasks = tdf.to_dict("records")
    team  = load_team(proj_id)
    acts  = load_activity(proj_id, 20)
    mets  = load_metrics(proj_id)

    total  = len(tasks)
    done   = sum(1 for t in tasks if t["status"]=="Done")
    inprog = sum(1 for t in tasks if t["status"]=="In Progress")
    todo   = sum(1 for t in tasks if t["status"]=="Todo")
    blk    = sum(1 for t in tasks if t["status"]=="Blocked")

    # Auto-detection scan
    if act and not tdf.empty:
        scan = auto_det.scan_sprint(tasks, act)
        ab   = scan["auto_blocked_count"]
        dl   = scan["delayed_count"]
        ar   = scan["at_risk_count"]
        if ab or dl or ar:
            st.markdown(f"""
            <div style="background:#1a0b0b;border:1px solid #f8514960;border-radius:8px;
                 padding:12px 16px;margin-bottom:16px;display:flex;gap:24px;align-items:center">
              <span style="color:#f85149;font-weight:700;font-size:14px">🤖 AI Auto-Detection</span>
              {'<span style="color:#f85149;font-size:13px">⛔ '+str(ab)+' task(s) auto-flagged as blocked</span>' if ab else ''}
              {'<span style="color:#d29922;font-size:13px">⏰ '+str(dl)+' task(s) delayed</span>' if dl else ''}
              {'<span style="color:#fbbf24;font-size:13px">⚠️ '+str(ar)+' at risk</span>' if ar else ''}
            </div>""", unsafe_allow_html=True)

    # KPI row
    k1,k2,k3,k4 = st.columns(4)
    def kcard(col, num, label, color):
        col.markdown(f'<div class="card"><div class="sum-num" style="color:{color}">{num}</div>'
                     f'<div class="sum-lbl">{label}</div></div>', unsafe_allow_html=True)
    kcard(k1, done,   "✅ Completed",   "#3fb950")
    kcard(k2, inprog, "◑ In Progress",  "#58a6ff")
    kcard(k3, todo,   "○ To Do",        "#8b949e")
    kcard(k4, blk,    "✕ Blocked",      "#f85149")
    # ADD THIS BELOW EXISTING CODE
    st.markdown("**Task Counts (Pending / In Progress / Completed)**")
    dc1, dc2, dc3 = st.columns(3)
    dc1.metric("Pending", todo)
    dc2.metric("In Progress", inprog)
    dc3.metric("Completed", done)

    fig_counts, ax_counts = plt.subplots(figsize=(3.2, 1.4), facecolor="none")
    labels = ["Pending", "In Progress", "Completed"]
    values = [todo, inprog, done]
    ax_counts.bar(labels, values, color=["#8b949e", "#58a6ff", "#3fb950"])
    ax_counts.set_facecolor("#0d1117")
    fig_counts.patch.set_alpha(0)
    ax_counts.tick_params(colors="#8b949e", labelsize=9)
    ax_counts.spines[:].set_color("#21262d")
    st.image(chart_buf(fig_counts), width=320)

    left, right = st.columns([1.4,1])

    with left:
        # Status donut
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**📊 Status Overview**")
        if total > 0:
            cl,cr=st.columns([1,1.1])
            with cl:
                fig,ax=plt.subplots(figsize=(3,3),facecolor='none')
                szs=[done,inprog,todo,blk]; cls=['#3fb950','#58a6ff','#8b949e','#f85149']
                lbls=['Done','In Progress','To Do','Blocked']
                nz=[(s,c,l) for s,c,l in zip(szs,cls,lbls) if s>0]
                if nz:
                    s2,c2,_=zip(*nz)
                    ax.pie(s2,colors=c2,startangle=90,wedgeprops=dict(width=0.45,edgecolor='#0d1117',linewidth=2))
                    ax.text(0,0,str(total),ha='center',va='center',fontsize=20,fontweight='bold',color='#e6edf3')
                ax.set_facecolor('none'); fig.patch.set_alpha(0)
                st.image(chart_buf(fig),use_container_width=True)
            with cr:
                for s,c,l in zip(szs,cls,lbls):
                    if s>0:
                        st.markdown(f"""
                        <div style="display:flex;align-items:center;gap:8px;margin-bottom:9px">
                          <div style="width:10px;height:10px;border-radius:2px;background:{c}"></div>
                          <span style="color:#c9d1d9;font-size:13px;flex:1">{l}</span>
                          <span style="color:#8b949e;font-size:12px">{s} ({s/total*100:.0f}%)</span>
                        </div>""", unsafe_allow_html=True)
        else:
            st.caption("No tasks yet.")
        st.markdown('</div>', unsafe_allow_html=True)

        # Priority breakdown
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**🎯 Priority Breakdown**")
        for pn,pc in [("Critical","#f85149"),("High","#d29922"),("Medium","#58a6ff"),("Low","#8b949e")]:
            cnt=sum(1 for t in tasks if t["priority"]==pn)
            if cnt:
                pct2=cnt/max(total,1)*100
                st.markdown(f"""
                <div style="margin-bottom:9px">
                  <div style="display:flex;justify-content:space-between;margin-bottom:3px">
                    <span style="color:#c9d1d9;font-size:12px">{pn}</span>
                    <span style="color:#8b949e;font-size:12px">{cnt} ({pct2:.0f}%)</span>
                  </div>
                  <div style="background:#21262d;border-radius:3px;height:5px">
                    <div style="width:{pct2}%;background:{pc};height:5px;border-radius:3px"></div>
                  </div>
                </div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        # ADD THIS BELOW EXISTING CODE
        rule_insights = generate_insights(tasks)
        blockers, blocker_warnings = detect_blockers(tasks)
        if rule_insights:
            st.markdown("**🧠 Rule-Based AI Insights**")
            for ins in rule_insights[:3]:
                st.markdown(f'<div class="rc rc-info">💡 {ins}</div>', unsafe_allow_html=True)
        if blocker_warnings:
            st.markdown("**🚧 Blocker Warnings**")
            for bw in blocker_warnings[:3]:
                st.markdown(f'<div class="rc rc-warn">⚠️ {bw}</div>', unsafe_allow_html=True)

        # AI sprint intelligence
        if act:
            hlth  = compute_sprint_health(tasks,act)
            s_risk= risk_det.assess_sprint_risk(act,tasks)
            vl    = mets["velocity"].tolist() if not mets.empty else [30,35,38,40]
            vfc   = vel_fc.forecast(vl)
            recs  = rec_eng.generate(s_risk,tasks,vfc,team.to_dict("records"))
            gc    = {"A":"#3fb950","B":"#d29922","C":"#f0883e","D":"#f85149","F":"#f85149"}.get(hlth["grade"],"#8b949e")
            rc    = {"low":"#3fb950","medium":"#d29922","high":"#f85149"}[s_risk["level"]]

            st.markdown(f"""
            <div class="card" style="margin-bottom:10px">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
                <span style="color:#e6edf3;font-weight:600;font-size:14px">🤖 AI Sprint Intelligence</span>
                <span style="background:{gc}20;color:{gc};border:1px solid {gc}40;border-radius:12px;padding:2px 10px;font-size:11px;font-weight:700">
                  Grade {hlth['grade']} · {hlth['score']}/100
                </span>
              </div>
              <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:10px">
                <div style="background:#21262d;border-radius:6px;padding:10px;text-align:center">
                  <div style="color:{rc};font-size:13px;font-weight:700">{s_risk['level'].upper()}</div>
                  <div style="color:#8b949e;font-size:10px">Sprint Risk</div>
                </div>
                <div style="background:#21262d;border-radius:6px;padding:10px;text-align:center">
                  <div style="color:#58a6ff;font-size:13px;font-weight:700">{vfc['forecast']}pt</div>
                  <div style="color:#8b949e;font-size:10px">Vel. Forecast</div>
                </div>
                <div style="background:#21262d;border-radius:6px;padding:10px;text-align:center">
                  <div style="color:#{'f85149' if blk>0 else '3fb950'};font-size:13px;font-weight:700">{blk}</div>
                  <div style="color:#8b949e;font-size:10px">Blockers</div>
                </div>
              </div>
            </div>""", unsafe_allow_html=True)

            rc_map={"warning":"rc-warn","caution":"rc-caut","action":"rc-act","info":"rc-info","success":"rc-ok"}
            st.markdown("**🔔 Recommendations**")
            for r in recs[:3]:
                st.markdown(f'<div class="rc {rc_map.get(r["type"],"rc-info")}"><strong>{r["icon"]} {r["title"]}</strong><br><span style="color:#8b949e">{r["body"]}</span></div>',unsafe_allow_html=True)

        # Activity feed
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**⚡ Recent Activity**")
        cmap={"K. Amulya":"#ec4899","M. Bhavani":"#3b82f6","B.G.L. Santhoshi":"#10b981","Mr. Sudheer":"#f59e0b"}
        if acts.empty:
            st.caption("No activity yet.")
        else:
            for _,a in acts.head(8).iterrows():
                actor=str(a.get("actor","System")); col=cmap.get(actor,"#8b949e")
                fld=a.get("field_changed",""); nv=a.get("new_value",""); tt=a.get("task_title",""); ts=str(a.get("created_at",""))[:16]
                desc=f'<b style="color:#58a6ff">{a.get("action","updated")}</b>'
                if fld and nv: desc+=f' <span style="color:#8b949e">{fld}</span> → <span style="color:#3fb950">{nv}</span>'
                if tt: desc+=f' on <b style="color:#c9d1d9">{tt}</b>'
                st.markdown(f"""
                <div class="act-row">
                  {av_html(actor,col,24)}
                  <div>
                    <span style="color:#c9d1d9;font-size:12px;font-weight:600">{actor}</span>
                    <span style="color:#8b949e;font-size:12px"> {desc}</span>
                    <div style="color:#8b949e;font-size:10px;margin-top:1px">{ts}</div>
                  </div>
                </div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # Velocity + Types row
    vc,tc=st.columns(2)
    with vc:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**📈 Velocity Trend**")
        if not mets.empty:
            mv=mets["velocity"].max()
            for _,r in mets.iterrows():
                v=r["velocity"]; p=r["planned_points"]; c2="#3fb950" if v>=p else "#d29922"
                st.markdown(f"""
                <div style="margin-bottom:8px">
                  <div style="display:flex;justify-content:space-between;margin-bottom:2px">
                    <span style="color:#8b949e;font-size:11px">{r['sprint_name']}</span>
                    <span style="color:{c2};font-size:11px;font-weight:600">{v:.0f}/{p:.0f}pt</span>
                  </div>
                  <div style="background:#21262d;border-radius:3px;height:5px">
                    <div style="width:{min(v/max(mv,1)*100,100):.0f}%;background:{c2};height:5px;border-radius:3px"></div>
                  </div>
                </div>""", unsafe_allow_html=True)
        else:
            st.caption("Complete sprints to see trend.")
        st.markdown('</div>', unsafe_allow_html=True)

    with tc:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**📦 Types of Work**")
        itcol={"Story":"#58a6ff","Task":"#3fb950","Bug":"#f85149","Subtask":"#d29922","Epic":"#a78bfa"}
        if not tdf.empty and "issue_type" in tdf.columns:
            for it,cnt in tdf["issue_type"].value_counts().items():
                c2=itcol.get(it,"#8b949e")
                st.markdown(f"""
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
                  <div style="width:8px;height:8px;border-radius:50%;background:{c2}"></div>
                  <span style="color:#c9d1d9;font-size:13px;flex:1">{it}</span>
                  <span style="color:#8b949e;font-size:12px">{cnt} ({cnt/max(total,1)*100:.0f}%)</span>
                </div>""", unsafe_allow_html=True)
        else:
            st.caption("No tasks yet.")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)  # page-wrap


# ══════════════════════════════════════════════════════════════════════════════
#  📋 LIST
# ══════════════════════════════════════════════════════════════════════════════
elif page == "List":
    st.markdown('<div class="page-wrap">', unsafe_allow_html=True)
    sdf=load_sprints(pid=proj_id); team=load_team(proj_id)
    act=load_active(proj_id)

    fc1,fc2,fc3,fc4,fc5=st.columns(5)
    f_spr=fc1.selectbox("Sprint",  ["All"]+(sdf["name"].tolist() if not sdf.empty else []))
    f_st =fc2.selectbox("Status",  ["All","Todo","In Progress","Done","Blocked"])
    f_pr =fc3.selectbox("Priority",["All","Critical","High","Medium","Low"])
    f_as =fc4.selectbox("Assignee",["All"]+(team["name"].tolist() if not team.empty else []))
    f_risk=fc5.selectbox("Risk",   ["All","Auto-Flagged","Delayed","At Risk"])

    all_t=load_tasks(project_id=proj_id)

    # Apply filters
    if not all_t.empty:
        if f_spr!="All" and not sdf.empty:
            sid2=int(sdf[sdf["name"]==f_spr]["id"].values[0]); all_t=all_t[all_t["sprint_id"]==sid2]
        if f_st !="All": all_t=all_t[all_t["status"]==f_st]
        if f_pr !="All": all_t=all_t[all_t["priority"]==f_pr]
        if f_as !="All": all_t=all_t[all_t["assignee_name"]==f_as]

    # Run auto-detection on filtered tasks
    scan_data = {}
    if act and not all_t.empty:
        sprint_for_scan = act
        scanned = auto_det.scan_sprint(all_t.to_dict("records"), sprint_for_scan)
        for t in scanned["tasks"]:
            scan_data[t["id"]] = t["auto_detection"]

    # Filter by risk
    if f_risk != "All" and scan_data:
        risk_filter_ids = set()
        for tid, det in scan_data.items():
            if f_risk == "Auto-Flagged" and det["auto_blocked"]:  risk_filter_ids.add(tid)
            if f_risk == "Delayed"      and det["delay_risk"]=="delayed": risk_filter_ids.add(tid)
            if f_risk == "At Risk"      and det["delay_risk"]=="at_risk": risk_filter_ids.add(tid)
        if risk_filter_ids:
            all_t = all_t[all_t["id"].isin(risk_filter_ids)]
        else:
            all_t = pd.DataFrame()

    st.caption(f"{len(all_t) if not all_t.empty else 0} items")

    if all_t.empty:
        st.info("No tasks match filters.")
    else:
        # Header row
        st.markdown("""
        <div style="display:grid;grid-template-columns:2fr 1fr 1fr 1fr 1fr 1fr 1fr;
             gap:6px;padding:8px 12px;background:#161b22;border:1px solid #30363d;
             border-radius:6px 6px 0 0;font-size:11px;color:#8b949e;font-weight:600;
             text-transform:uppercase;letter-spacing:.5px">
          <div>Title</div><div>Assignee</div><div>Priority</div><div>Status</div>
          <div>AI Risk</div><div>Points</div><div>Est. Hrs</div>
        </div>""", unsafe_allow_html=True)

        for _,t in all_t.iterrows():
            det  = scan_data.get(t["id"], {})
            ab   = det.get("auto_blocked", False)
            dr   = det.get("delay_risk","none")
            av   = t.get("assignee_name") or "Unassigned"
            avc  = t.get("avatar_color") or "#8b949e"
            reasons = det.get("reasons",[])

            risk_label = '🤖 <span style="color:#e879f9">AUTO-FLAGGED</span>' if ab else \
                         '⏰ <span style="color:#f85149">DELAYED</span>'     if dr=="delayed" else \
                         '⚠️ <span style="color:#d29922">AT RISK</span>'      if dr=="at_risk" else \
                         '🟢 <span style="color:#3fb950">OK</span>'
            border_col = "#f85149" if ab or dr=="delayed" else "#d29922" if dr=="at_risk" else "#21262d"

            blocker_html = f'<div style="color:#f85149;font-size:10px;margin-top:2px">⛔ {t["blocker_note"]}</div>' if t.get("blocker_note") else ''
            reason_html  = f'<div style="color:#d29922;font-size:10px;margin-top:2px">🤖 {reasons[0]}</div>' if reasons else ''

            st.markdown(
                f'<div style="display:grid;grid-template-columns:2fr 1fr 1fr 1fr 1fr 1fr 1fr;gap:6px;padding:10px 12px;background:#0d1117;border:1px solid #21262d;border-top:none;border-left:3px solid {border_col};font-size:13px">'
                f'<div style="color:#e6edf3;font-weight:500">{t["title"]}{blocker_html}{reason_html}</div>'
                f'<div style="display:flex;align-items:center;gap:5px">{av_html(av,avc,18)} <span style="color:#8b949e;font-size:11px">{av}</span></div>'
                f'<div>{pbadge(t["priority"])}</div>'
                f'<div>{sbadge(t["status"])}</div>'
                f'<div style="font-size:11px">{risk_label}</div>'
                f'<div style="color:#8b949e">{t.get("story_points",1)}pt</div>'
                f'<div style="color:#8b949e">{t.get("estimated_hours") or "—"}h</div>'
                f'</div>',
                unsafe_allow_html=True
            )

        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("✏️ Edit a Task"):
            opts2=member_opts(team)
            with st.form("le"):
                sel_t=st.selectbox("Task",all_t["title"].tolist())
                trow=all_t[all_t["title"]==sel_t].iloc[0]
                lc1,lc2,lc3=st.columns(3)
                ns=lc1.selectbox("Status",["Todo","In Progress","Done","Blocked"],index=["Todo","In Progress","Done","Blocked"].index(trow["status"]))
                np2=lc2.selectbox("Priority",["Low","Medium","High","Critical"],index=["Low","Medium","High","Critical"].index(trow["priority"]))
                na=lc3.selectbox("Assignee",list(opts2.keys()),format_func=lambda x:opts2[x])
                nah=st.number_input("Actual Hours",0.0,200.0,float(trow.get("actual_hours") or 0.0),step=0.5)
                nbl=st.text_input("Blocker Note",value=trow.get("blocker_note") or "")
                if st.form_submit_button("💾 Save",type="primary"):
                    exe("UPDATE tasks SET status=?,priority=?,assignee_id=?,actual_hours=?,blocker_note=?,updated_at=datetime('now') WHERE id=?",
                        (ns,np2,na,nah or None,nbl or None,int(trow["id"])))
                    if ns!=trow["status"] and trow.get("sprint_id"):
                        if ns=="Done":    exe("UPDATE sprints SET completed_points=completed_points+? WHERE id=?",(int(trow["story_points"]),int(trow["sprint_id"])))
                        elif trow["status"]=="Done": exe("UPDATE sprints SET completed_points=MAX(0,completed_points-?) WHERE id=?",(int(trow["story_points"]),int(trow["sprint_id"])))
                    log_activity(proj_id,opts2.get(na,"User").split(" (")[0],"updated",trow["title"],"status",trow["status"],int(trow["id"]),trow.get("sprint_id"),trow["title"])
                    st.success("Saved!"); st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  🗂️ BOARD
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Board":
    st.markdown('<div class="page-wrap">', unsafe_allow_html=True)
    sdf=load_sprints(pid=proj_id); team=load_team(proj_id)
    if sdf.empty: st.warning("No sprints yet. Go to **Sprints** to create one."); st.stop()

    names=sdf["name"].tolist()
    def_idx=next((i for i,s in enumerate(sdf["status"]) if s=="Active"),0)
    sel=st.selectbox("Sprint",names,index=def_idx)
    srow=sdf[sdf["name"]==sel].iloc[0]; sid=int(srow["id"])
    st.caption(f"📅 {srow['start_date']} → {srow['end_date']}  ·  Status: **{srow['status']}**  ·  Goal: *{srow.get('goal') or '—'}*")

    tdf=load_tasks(sprint_id=sid); tasks=tdf.to_dict("records")

    # Auto-detect
    scan2={}
    if not tdf.empty:
        sc=auto_det.scan_sprint(tasks, srow.to_dict())
        if sc["auto_blocked_count"] or sc["delayed_count"]:
            st.markdown(f"""
            <div style="background:#1a0b0b;border:1px solid #f8514960;border-radius:8px;
                 padding:10px 16px;margin-bottom:12px;display:flex;gap:20px;align-items:center">
              <span style="color:#f85149;font-weight:700">🤖 AI Detected:</span>
              {'<span style="color:#f85149;font-size:13px">⛔ '+str(sc["auto_blocked_count"])+' auto-flagged</span>' if sc["auto_blocked_count"] else ''}
              {'<span style="color:#d29922;font-size:13px">⏰ '+str(sc["delayed_count"])+' delayed</span>' if sc["delayed_count"] else ''}
              {'<span style="color:#fbbf24;font-size:13px">⚠️ '+str(sc["at_risk_count"])+' at risk</span>' if sc["at_risk_count"] else ''}
              <span style="color:#8b949e;font-size:12px">See AI Insights tab for details →</span>
            </div>""", unsafe_allow_html=True)
        for t in sc["tasks"]:
            scan2[t["id"]] = t["auto_detection"]

    with st.expander("✏️ Update Task Status / Log Hours"):
        if tdf.empty: st.caption("No tasks.")
        else:
            with st.form("bu"):
                titles=tdf["title"].tolist(); ids=tdf["id"].tolist()
                sel_t=st.selectbox("Task",titles); tid=ids[titles.index(sel_t)]
                cur=tdf[tdf["id"]==tid].iloc[0]
                uc1,uc2,uc3=st.columns(3)
                ns=uc1.selectbox("Status",["Todo","In Progress","Done","Blocked"],index=["Todo","In Progress","Done","Blocked"].index(cur["status"]))
                na=uc2.number_input("Actual Hours",0.0,200.0,float(cur.get("actual_hours") or 0.0),step=0.5)
                nb=uc3.text_input("Blocker Note",value=cur.get("blocker_note") or "")
                if st.form_submit_button("💾 Save",type="primary"):
                    exe("UPDATE tasks SET status=?,actual_hours=?,blocker_note=?,updated_at=datetime('now') WHERE id=?",
                        (ns,na or None,nb or None,tid))
                    if ns!=cur["status"]:
                        if ns=="Done":    exe("UPDATE sprints SET completed_points=completed_points+? WHERE id=?",(int(cur["story_points"]),sid))
                        elif cur["status"]=="Done": exe("UPDATE sprints SET completed_points=MAX(0,completed_points-?) WHERE id=?",(int(cur["story_points"]),sid))
                    log_activity(proj_id,"User","updated",sel_t,"status",cur["status"],int(cur["id"]),sid,sel_t)
                    st.success("Updated!"); st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    COLS=["Todo","In Progress","Done","Blocked"]
    BORDS={"Todo":"#475569","In Progress":"#2563eb","Done":"#059669","Blocked":"#dc2626"}
    cws=st.columns(4)
    for idx,status in enumerate(COLS):
        col_t=[t for t in tasks if t["status"]==status]; pts=sum(t["story_points"] for t in col_t); bc=BORDS[status]
        with cws[idx]:
            st.markdown(f"""
            <div style="background:#161b22;border:1px solid {bc}50;border-top:3px solid {bc};
                 border-radius:8px;padding:8px 12px;margin-bottom:8px;
                 display:flex;justify-content:space-between;align-items:center">
              <span style="color:#e6edf3;font-weight:600;font-size:13px">{status}</span>
              <span style="background:{bc}25;border-radius:10px;padding:1px 8px;font-size:11px;color:#c9d1d9">{len(col_t)}·{pts}pt</span>
            </div>""", unsafe_allow_html=True)

            if not col_t:
                st.markdown('<div style="color:#30363d;text-align:center;padding:28px;font-size:12px;border:1px dashed #21262d;border-radius:6px">— empty —</div>',unsafe_allow_html=True)

            for t in col_t:
                det2=scan2.get(t["id"],{})
                ab2=det2.get("auto_blocked",False); dr2=det2.get("delay_risk","none")
                ai_reasons=det2.get("reasons",[])
                bord_c="#e879f9" if ab2 else "#f85149" if dr2=="delayed" else "#d29922" if dr2=="at_risk" else "#3b82f640"
                if ab2:   ai_banner='<div style="color:#e879f9;font-size:10px;margin-top:3px">🤖 AI: Auto-flagged as blocked</div>'
                elif dr2=="delayed": ai_banner=f'<div style="color:#f85149;font-size:10px;margin-top:3px">⏰ Delayed ~{det2.get("delay_days",0)}d</div>'
                elif dr2=="at_risk": ai_banner=f'<div style="color:#d29922;font-size:10px;margin-top:3px">⚠️ {ai_reasons[0] if ai_reasons else "At risk"}</div>'
                else: ai_banner=""
                blk_note=f'<div style="color:#f85149;font-size:10px;margin-top:3px;padding-top:3px;border-top:1px solid #30363d">⛔ {t["blocker_note"]}</div>' if t.get("blocker_note") else ""
                av=t.get("assignee_name") or "Unassigned"; avc=t.get("avatar_color") or "#8b949e"
                st.markdown(
                    f'<div style="background:#161b22;border:1px solid {bord_c};border-radius:6px;padding:10px 12px;margin-bottom:6px">'
                    f'<div style="color:#e6edf3;font-weight:500;font-size:13px;margin-bottom:5px">{t["title"]}</div>'
                    f'<div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:5px">{pbadge(t["priority"])}<span class="badge s-todo" style="font-size:10px">{t["story_points"]}pt</span></div>'
                    f'<div style="display:flex;align-items:center;gap:5px">{av_html(av,avc,18)} <span style="color:#8b949e;font-size:11px">{av}</span></div>'
                    f'{ai_banner}{blk_note}'
                    f'</div>',
                    unsafe_allow_html=True
                )
    st.markdown('</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  🏃 SPRINTS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Sprints":
    st.markdown('<div class="page-wrap">', unsafe_allow_html=True)
    if st.session_state.get("role") == "Manager":
        with st.expander("➕ Create New Sprint",expanded=True):
            with st.form("cs"):
                st.markdown("#### New Sprint")
                sc1,sc2=st.columns(2)
                sn=sc1.text_input("Sprint Name *",placeholder="Sprint 1"); sg=sc1.text_input("Sprint Goal",placeholder="e.g. Complete auth module")
                ss=sc2.date_input("Start Date",value=date.today()); se=sc2.date_input("End Date",value=date.today()+timedelta(days=14))
                sp=sc2.number_input("Planned Story Points",10,200,40)
                if st.form_submit_button("🚀 Create Sprint",type="primary"):
                    if not sn.strip(): st.error("Name required.")
                    elif se<=ss: st.error("End must be after start.")
                    else:
                        ex=load_sprints(pid=proj_id)
                        if not ex.empty and sn.strip() in ex["name"].tolist(): st.error("Name exists.")
                        else:
                            exe("INSERT INTO sprints(project_id,name,goal,start_date,end_date,status,planned_points,completed_points)VALUES(?,?,?,?,?,?,?,?)",
                                (proj_id,sn.strip(),sg.strip(),str(ss),str(se),"Planning",sp,0))
                            log_activity(proj_id,"User","created sprint",sn.strip())
                            st.success(f"Sprint '{sn}' created!"); st.rerun()
    else:
        st.caption("Member access: sprint creation is restricted.")

    st.divider()
    sdf=load_sprints(pid=proj_id)
    if sdf.empty: st.info("No sprints yet."); st.markdown('</div>',unsafe_allow_html=True); st.stop()

    for _,s in sdf.iterrows():
        sid2=int(s["id"]); stask=load_tasks(sprint_id=sid2)
        dp=int(s["completed_points"]); pp=int(s["planned_points"]); pct=dp/max(pp,1)*100
        icon={"Planning":"🔵","Active":"🟢","Completed":"✅"}.get(s["status"],"⚪")
        with st.expander(f"{icon} **{s['name']}**  ·  {s['status']}  ·  {dp}/{pp} pts  ·  {s['start_date']} → {s['end_date']}",expanded=(s["status"]=="Active")):
            el,er=st.columns([2,1])
            with el:
                st.markdown(f"**Goal:** {s.get('goal') or '—'}"); st.progress(min(pct/100,1.0),text=f"{pct:.0f}% · {len(stask)} tasks")
                with st.form(f"es_{sid2}"):
                    c1,c2=st.columns(2)
                    en=c1.text_input("Name",value=s["name"]); eg=c1.text_input("Goal",value=s.get("goal") or "")
                    esd=c2.date_input("Start",value=pd.to_datetime(s["start_date"]).date()); eed=c2.date_input("End",value=pd.to_datetime(s["end_date"]).date())
                    ep=c2.number_input("Planned Pts",10,300,int(s["planned_points"]))
                    if st.form_submit_button("💾 Save"):
                        exe("UPDATE sprints SET name=?,goal=?,start_date=?,end_date=?,planned_points=? WHERE id=?",(en,eg,str(esd),str(eed),ep,sid2)); st.success("Updated!"); st.rerun()
            with er:
                st.markdown("**Actions**")
                if st.session_state.get("role") == "Manager":
                    if s["status"]=="Planning":
                        if load_active(proj_id): st.warning("Another sprint is active.")
                        elif st.button("▶️ Start Sprint",key=f"st_{sid2}",type="primary"):
                            exe("UPDATE sprints SET status='Active' WHERE id=?",(sid2,)); log_activity(proj_id,"User","started sprint",s["name"]); st.success("Started!"); st.rerun()
                    if s["status"]=="Active":
                        if st.button("✅ Complete Sprint",key=f"cp_{sid2}",type="primary"):
                            exe("UPDATE tasks SET sprint_id=NULL WHERE sprint_id=? AND status!='Done'",(sid2,))
                            exe("UPDATE sprints SET status='Completed' WHERE id=?",(sid2,))
                            tl=stask.to_dict("records"); dc=sum(1 for t in tl if t["status"]=="Done"); bc=sum(1 for t in tl if t["status"]=="Blocked")
                            exe("INSERT OR REPLACE INTO sprint_metrics(sprint_id,velocity,completion_rate,avg_cycle_time,blockers_count,on_time_tasks,late_tasks)VALUES(?,?,?,?,?,?,?)",
                                (sid2,dp,round(dp/max(pp,1)*100,1),2.5,bc,dc,len(tl)-dc))
                            log_activity(proj_id,"User","completed sprint",s["name"]); st.success("Completed!"); st.rerun()
                    if s["status"]=="Planning" and st.button("🗑️ Delete",key=f"dl_{sid2}"):
                        exe("DELETE FROM sprint_metrics WHERE sprint_id=?",(sid2,)); exe("UPDATE tasks SET sprint_id=NULL WHERE sprint_id=?",(sid2,)); exe("DELETE FROM sprints WHERE id=?",(sid2,)); st.success("Deleted."); st.rerun()
                else:
                    st.caption("Member access: sprint actions are restricted.")
            st.divider(); st.markdown("**📥 Add Backlog Tasks**")
            backlog=qry("SELECT id,title,priority,story_points FROM tasks WHERE project_id=? AND (sprint_id IS NULL OR sprint_id=0)",[proj_id])
            if backlog.empty: st.caption("No unassigned tasks.")
            else:
                if st.session_state.get("role") == "Manager":
                    with st.form(f"at_{sid2}"):
                        sel_t2=st.multiselect("Select tasks",backlog["title"].tolist())
                        if st.form_submit_button("📥 Add to Sprint"):
                            for tit in sel_t2:
                                tr2=backlog[backlog["title"]==tit].iloc[0]; exe("UPDATE tasks SET sprint_id=? WHERE id=?",(sid2,int(tr2["id"]))); exe("UPDATE sprints SET planned_points=planned_points+? WHERE id=?",(int(tr2["story_points"]),sid2))
                            st.success(f"Added {len(sel_t2)}!"); st.rerun()
                else:
                    st.caption("Member access: backlog-to-sprint assignment is restricted.")
            if not stask.empty:
                sc2b=["title","assignee_name","priority","status","story_points"]
                st.dataframe(stask[[c for c in sc2b if c in stask.columns]].fillna("—"),use_container_width=True,hide_index=True)
    st.markdown('</div>',unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  🗒️ TASK CREATION
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Task Creation":
    st.markdown('<div class="page-wrap">', unsafe_allow_html=True)
    team=load_team(proj_id); sdf=load_sprints(pid=proj_id); opts2=member_opts(team)

    if st.session_state.get("role") == "Manager":
        with st.expander("➕ Create New Task",expanded=True):
            with st.form("ct"):
                st.markdown("#### New Task")
                r1,r2=st.columns(2)
                t_tit=r1.text_input("Title *",placeholder="e.g. Implement login API")
                t_des=r1.text_area("Description",height=70,placeholder="What needs to be done?")
                t_typ=r1.selectbox("Issue Type",["Story","Task","Bug","Subtask","Epic"])
                t_tag=r1.text_input("Labels / Tags",placeholder="backend, api")
                t_spr=r2.selectbox("Sprint",[None]+(sdf["id"].tolist() if not sdf.empty else []),format_func=lambda x:"— Backlog —" if x is None else sdf[sdf["id"]==x]["name"].values[0])
                t_as=r2.selectbox("Assignee",list(opts2.keys()),format_func=lambda x:opts2[x])
                t_pr=r2.selectbox("Priority",["Medium","Low","High","Critical"])
                t_sp=r2.selectbox("Story Points",[1,2,3,5,8,13],index=2)
                t_eh=r2.number_input("Estimated Hours",0.5,200.0,float(t_sp*2),step=0.5)
                t_bl=r2.text_input("Blocker Note (optional)","")
                if st.form_submit_button("➕ Create Task",type="primary"):
                    if not t_tit.strip(): st.error("Title required.")
                    else:
                        vel3=14.0
                        if t_as:
                            row3=team[team["id"]==t_as]
                            if not row3.empty: vel3=float(row3["velocity_avg"].values[0])
                        cap=40
                        if t_spr and not sdf.empty:
                            sr3=sdf[sdf["id"]==t_spr]
                            if not sr3.empty: cap=int(sr3["planned_points"].values[0])
                        pred=get_predictor_for_project(proj_id)[0].predict(t_sp,t_eh,t_pr,vel3,cap)
                        init="Blocked" if t_bl.strip() else "Todo"
                        nid=exe("INSERT INTO tasks(sprint_id,project_id,title,description,assignee_id,priority,status,issue_type,story_points,estimated_hours,tags,blocker_note)VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                                (t_spr,proj_id,t_tit.strip(),t_des.strip(),t_as,t_pr,init,t_typ,t_sp,t_eh,t_tag.strip(),t_bl.strip() or None))
                        if t_spr: exe("UPDATE sprints SET planned_points=planned_points+? WHERE id=?",(t_sp,t_spr))
                        actor=opts2.get(t_as,"User").split(" (")[0]
                        log_activity(proj_id,actor,"created",t_tit.strip(),"status","Todo",nid,t_spr,t_tit.strip())
                        c1,c2,c3=st.columns(3)
                        c1.metric("AI Predicted",f"{pred}h"); c2.metric("Your Estimate",f"{t_eh}h"); c3.metric("Difference",f"{pred-t_eh:+.1f}h")
                        risk4=risk_det.assess_task_risk({"priority":t_pr,"status":init,"story_points":t_sp,"estimated_hours":t_eh,"assignee_id":t_as},vel3,7)
                        ri4={"low":"🟢","medium":"🟡","high":"🔴"}[risk4["level"]]
                        st.info(f"AI Risk: {ri4} **{risk4['level'].upper()}**" + (f"  — {risk4['reasons'][0]}" if risk4["reasons"] else ""))
                        st.success(f"Task '{t_tit}' created (ID {nid})"); st.rerun()
    else:
        st.caption("Member access: task creation is restricted.")

    st.divider()
    fc1,fc2,fc3,fc4=st.columns(4)
    f_s2=fc1.selectbox("Sprint",["All"]+(sdf["name"].tolist() if not sdf.empty else []),key="bf1")
    f_st2=fc2.selectbox("Status",["All","Todo","In Progress","Done","Blocked"],key="bf2")
    f_p2=fc3.selectbox("Priority",["All","Critical","High","Medium","Low"],key="bf3")
    f_a2=fc4.selectbox("Assignee",["All"]+(team["name"].tolist() if not team.empty else []),key="bf4")

    all_t2=load_tasks(project_id=proj_id)
    if not all_t2.empty:
        if f_s2!="All" and not sdf.empty:
            sid3=int(sdf[sdf["name"]==f_s2]["id"].values[0]); all_t2=all_t2[all_t2["sprint_id"]==sid3]
        if f_st2!="All": all_t2=all_t2[all_t2["status"]==f_st2]
        if f_p2!="All":  all_t2=all_t2[all_t2["priority"]==f_p2]
        if f_a2!="All":  all_t2=all_t2[all_t2["assignee_name"]==f_a2]

    if all_t2.empty: st.caption("No tasks.")
    else:
        st.caption(f"{len(all_t2)} task(s)")
        PRI_ICON = {"Critical":"🔴","High":"🟡","Medium":"🔵","Low":"⚪"}
        STS_ICON = {"Done":"✅","In Progress":"⏳","Todo":"○","Blocked":"⛔"}
        for _,t in all_t2.iterrows():
            pri_txt = PRI_ICON.get(t['priority'],'') + ' ' + t['priority']
            sts_txt = STS_ICON.get(t['status'],'') + ' ' + t['status']
            av_txt  = t.get('assignee_name') or 'Unassigned'
            label   = f"{pri_txt}  {t['title']}  ·  {sts_txt}  ·  {t['story_points']}pt  ·  👤 {av_txt}"
            with st.expander(label, expanded=False):
                dc1,dc2=st.columns(2)
                with dc1:
                    st.markdown(f"**Desc:** {t.get('description') or '—'}")
                    st.markdown(f"**Tags:** `{t.get('tags') or '—'}` · **Type:** `{t.get('issue_type','Task')}`")
                    st.markdown(f"**Est:** {t.get('estimated_hours') or '—'}h · **Actual:** {t.get('actual_hours') or '—'}h")
                    if t.get("blocker_note"): st.error(f"⛔ {t['blocker_note']}")
                with dc2:
                    with st.form(f"te_{t['id']}"):
                        e_t=st.text_input("Title",value=t["title"],key=f"ett_{t['id']}")
                        e_s=st.selectbox("Status",["Todo","In Progress","Done","Blocked"],index=["Todo","In Progress","Done","Blocked"].index(t["status"]),key=f"ets_{t['id']}")
                        e_p=st.selectbox("Priority",["Low","Medium","High","Critical"],index=["Low","Medium","High","Critical"].index(t["priority"]),key=f"etp_{t['id']}")
                        e_a=st.selectbox("Assignee",list(opts2.keys()),format_func=lambda x:opts2[x],index=list(opts2.keys()).index(t["assignee_id"]) if t["assignee_id"] in list(opts2.keys()) else 0,key=f"eta_{t['id']}")
                        e_sp2=st.selectbox("Pts",[1,2,3,5,8,13],index=[1,2,3,5,8,13].index(int(t["story_points"])) if int(t["story_points"]) in [1,2,3,5,8,13] else 2,key=f"etsp_{t['id']}")
                        e_eh=st.number_input("Est.h",0.5,200.0,float(t.get("estimated_hours") or 2.0),step=0.5,key=f"eteh_{t['id']}")
                        e_ah=st.number_input("Act.h",0.0,200.0,float(t.get("actual_hours") or 0.0),step=0.5,key=f"etah_{t['id']}")
                        e_bl=st.text_input("Blocker",value=t.get("blocker_note") or "",key=f"etbl_{t['id']}")
                        sp_map={None:"— Backlog —"};sp_map.update({r["id"]:r["name"] for _,r in sdf.iterrows()} if not sdf.empty else {})
                        cur_spr=t["sprint_id"] if t["sprint_id"] in list(sp_map.keys()) else None
                        e_spr2=st.selectbox("Sprint",list(sp_map.keys()),format_func=lambda x:sp_map[x],index=list(sp_map.keys()).index(cur_spr),key=f"etspr_{t['id']}")
                        sv,dl=st.columns(2)
                        if sv.form_submit_button("💾",type="primary"):
                            old_pts=int(t["story_points"])
                            exe("UPDATE tasks SET title=?,status=?,priority=?,assignee_id=?,story_points=?,estimated_hours=?,actual_hours=?,blocker_note=?,sprint_id=?,updated_at=datetime('now') WHERE id=?",
                                (e_t,e_s,e_p,e_a,e_sp2,e_eh,e_ah or None,e_bl or None,e_spr2,int(t["id"])))
                            if t.get("sprint_id") and t["sprint_id"]!=e_spr2: exe("UPDATE sprints SET planned_points=MAX(0,planned_points-?) WHERE id=?",(old_pts,int(t["sprint_id"])))
                            if e_spr2 and e_spr2!=t.get("sprint_id"): exe("UPDATE sprints SET planned_points=planned_points+? WHERE id=?",(e_sp2,e_spr2))
                            if e_s=="Done" and t["status"]!="Done" and e_spr2: exe("UPDATE sprints SET completed_points=completed_points+? WHERE id=?",(e_sp2,e_spr2))
                            elif t["status"]=="Done" and e_s!="Done" and e_spr2: exe("UPDATE sprints SET completed_points=MAX(0,completed_points-?) WHERE id=?",(e_sp2,e_spr2))
                            log_activity(proj_id,opts2.get(e_a,"User").split(" (")[0],"updated",e_t,"status",t["status"],int(t["id"]),e_spr2,e_t)
                            st.success("Saved!"); st.rerun()
                        if dl.form_submit_button("🗑️"):
                            if t.get("sprint_id"):
                                exe("UPDATE sprints SET planned_points=MAX(0,planned_points-?) WHERE id=?",(int(t["story_points"]),int(t["sprint_id"])))
                                if t["status"]=="Done": exe("UPDATE sprints SET completed_points=MAX(0,completed_points-?) WHERE id=?",(int(t["story_points"]),int(t["sprint_id"])))
                            exe("DELETE FROM tasks WHERE id=?",(int(t["id"]),)); st.success("Deleted."); st.rerun()
    st.markdown('</div>',unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  👥 TEAM
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Team":
    st.markdown('<div class="page-wrap">', unsafe_allow_html=True)
    team=load_team(proj_id); act=load_active(proj_id); tdf=load_tasks(sprint_id=act["id"]) if act else pd.DataFrame()
    ROLES=["Frontend Developer","Backend Developer","Full Stack Developer","ML Engineer","Data Scientist","DevOps Engineer","QA Engineer","Scrum Master","Product Owner","Tech Lead"]
    AVCOLS=["#ec4899","#3b82f6","#10b981","#f59e0b","#8b5cf6","#06b6d4","#f43f5e","#84cc16"]

    with st.expander("➕ Add Team Member",expanded=team.empty):
        with st.form("am"):
            mc1,mc2,mc3=st.columns(3)
            mn=mc1.text_input("Full Name *"); mr=mc2.selectbox("Role",ROLES); mv=mc3.number_input("Velocity",1.0,60.0,12.0,step=0.5)
            if st.form_submit_button("➕ Add",type="primary"):
                if not mn.strip(): st.error("Name required.")
                elif not team.empty and mn.strip() in team["name"].tolist(): st.error("Already exists.")
                else:
                    col2=AVCOLS[len(team)%len(AVCOLS)]
                    exe("INSERT INTO team_members(name,role,velocity_avg,project_id,avatar_color)VALUES(?,?,?,?,?)",(mn.strip(),mr,mv,proj_id,col2))
                    log_activity(proj_id,mn.strip(),"joined team"); st.success(f"✅ {mn} added!"); st.rerun()

    st.divider()
    if team.empty: st.info("No team members yet."); st.markdown('</div>',unsafe_allow_html=True); st.stop()

    rows=[]
    for _,m in team.iterrows():
        mt=tdf[tdf["assignee_id"]==m["id"]] if not tdf.empty else pd.DataFrame()
        rows.append({"Name":m["name"],"Role":m["role"],"Velocity":m["velocity_avg"],"Sprint Tasks":len(mt),
                     "Done":len(mt[mt["status"]=="Done"]) if not mt.empty else 0,"Blocked":len(mt[mt["status"]=="Blocked"]) if not mt.empty else 0})
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    st.divider()

    for i,(_,m) in enumerate(team.iterrows()):
        avc=m.get("avatar_color","#3b82f6"); mt=tdf[tdf["assignee_id"]==m["id"]] if not tdf.empty else pd.DataFrame()
        with st.expander(f"  **{m['name']}**  ·  {m['role']}  ·  ⚡ {m['velocity_avg']}pt",expanded=False):
            ec1,ec2=st.columns([1.5,1])
            with ec1:
                if not mt.empty:
                    sc3=["title","priority","status","story_points"]
                    st.dataframe(mt[[c for c in sc3 if c in mt.columns]].fillna("—"),use_container_width=True,hide_index=True)
                else: st.caption("No tasks this sprint.")
            with ec2:
                with st.form(f"em_{m['id']}"):
                    en2=st.text_input("Name",value=m["name"]); er2=st.selectbox("Role",ROLES,index=ROLES.index(m["role"]) if m["role"] in ROLES else 0)
                    ev2=st.number_input("Velocity",1.0,60.0,float(m["velocity_avg"]),step=0.5)
                    sv3,rm3=st.columns(2)
                    if sv3.form_submit_button("💾 Save",type="primary"):
                        exe("UPDATE team_members SET name=?,role=?,velocity_avg=? WHERE id=?",(en2,er2,ev2,int(m["id"]))); st.success("Saved!"); st.rerun()
                    if rm3.form_submit_button("🗑️ Remove"):
                        exe("UPDATE tasks SET assignee_id=NULL WHERE assignee_id=?",(int(m["id"]),)); exe("DELETE FROM team_members WHERE id=?",(int(m["id"]),)); st.success("Removed."); st.rerun()
    st.markdown('</div>',unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  🔮 AI INSIGHTS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "AI Insights":
    st.markdown('<div class="page-wrap">', unsafe_allow_html=True)
    st.markdown("### 🔮 AI Insights & Predictions")
    st.caption("Auto-Blocker Detection · Time Predictor · Velocity Forecast · Risk Scoring")

    act=load_active(proj_id); team=load_team(proj_id)
    tab1,tab2,tab3,tab4,tab5=st.tabs(["🤖 Auto Detection","⏱️ Time Predictor","📈 Velocity","🔍 Risk","💡 Recommendations"])

    with tab1:
        st.subheader("🤖 Automatic Blocker & Delay Detection")
        st.markdown("""
        <div class="rc rc-act">
          <strong>How it works — No manual input needed</strong><br>
          <span style="color:#8b949e">The AI continuously monitors all tasks and automatically flags them based on:
          stagnation (no updates in 2+ days), hour overruns (actual > 130% of estimate),
          deadline proximity (not started with &lt;3 days left),
          high-priority tasks past sprint midpoint, and velocity mismatches.</span>
        </div>""", unsafe_allow_html=True)

        if not act:
            st.info("No active sprint to analyze.")
        else:
            tdf5=load_tasks(sprint_id=act["id"]); tasks5=tdf5.to_dict("records")
            scan5=auto_det.scan_sprint(tasks5, act)

            c1,c2,c3,c4=st.columns(4)
            c1.metric("Auto-Flagged",  scan5["auto_blocked_count"], help="Tasks AI detected as effectively blocked")
            c2.metric("Delayed",       scan5["delayed_count"],      help="Tasks predicted to miss deadline")
            c3.metric("At Risk",       scan5["at_risk_count"],      help="Tasks showing warning signs")
            c4.metric("Days Remaining",scan5["remaining_days"])

            st.divider()
            flagged=[t for t in scan5["tasks"] if t["auto_detection"]["delay_risk"]!="none" or t["auto_detection"]["auto_blocked"]]
            if not flagged:
                st.markdown('<div class="rc rc-ok">✅ No issues auto-detected. All tasks look on track.</div>',unsafe_allow_html=True)
            else:
                for t in flagged:
                    det=t["auto_detection"]; ab=det["auto_blocked"]; dr=det["delay_risk"]
                    css="auto-blk" if ab or dr=="delayed" else "auto-risk"
                    bc="#f85149" if ab or dr=="delayed" else "#d29922"
                    av=t.get("assignee_name") or "Unassigned"; avc=t.get("avatar_color") or "#8b949e"
                    reasons_html="".join(f'<li style="color:#c9d1d9;font-size:12px">{r}</li>' for r in det["reasons"])
                    sugg_html="".join(f'<li style="color:#58a6ff;font-size:12px">💡 {s}</li>' for s in det["suggestions"])
                    delay_badge=f'<span style="color:#f85149;font-size:11px;font-weight:700">~{det["delay_days"]}d delay</span>' if det["delay_days"]>0 else ""
                    status_label = '⛔ AUTO-BLOCKED' if ab else '⏰ DELAYED' if dr=='delayed' else '⚠️ AT RISK'
                    st.markdown(
                        f'<div class="{css}" style="margin-bottom:10px">'
                        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">'
                        f'<div><span style="color:{bc};font-weight:700;font-size:14px">{status_label}</span>'
                        f'<span style="color:#e6edf3;font-size:13px;font-weight:500;margin-left:8px">{t["title"]}</span></div>'
                        f'<div style="display:flex;gap:6px;align-items:center">{delay_badge}{av_html(av,avc,22)}'
                        f'<span style="color:#8b949e;font-size:11px">{av}</span>{pbadge(t["priority"])}</div>'
                        f'</div>'
                        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">'
                        f'<div><div style="color:#8b949e;font-size:11px;font-weight:600;margin-bottom:3px">REASONS DETECTED</div>'
                        f'<ul style="margin:0;padding-left:14px">{reasons_html}</ul></div>'
                        f'<div><div style="color:#8b949e;font-size:11px;font-weight:600;margin-bottom:3px">AI SUGGESTIONS</div>'
                        f'<ul style="margin:0;padding-left:14px">{sugg_html}</ul></div>'
                        f'</div></div>',
                        unsafe_allow_html=True
                    )

    with tab2:
        st.subheader("⏱️ Task Completion Time Predictor")

        # Train predictor on THIS project's data only
        proj_predictor, hist_count = get_predictor_for_project(proj_id)

        if proj_predictor.trained:
            st.success(f"✅ Random Forest trained on **{hist_count} tasks** from this project  |  MAE: **{proj_predictor.mae}h**")
            imps = proj_predictor.feature_importances()
            if imps:
                fig4,ax4=plt.subplots(figsize=(6,2.5),facecolor='none')
                imp_df=pd.DataFrame({"Feature":list(imps.keys()),"Importance":list(imps.values())}).sort_values("Importance")
                ax4.barh(imp_df["Feature"],imp_df["Importance"],color='#58a6ff',height=0.5)
                ax4.set_facecolor('#0d1117'); fig4.patch.set_alpha(0)
                ax4.tick_params(colors='#8b949e',labelsize=9); ax4.spines[:].set_color('#21262d')
                ax4.set_xlabel("Importance",color='#8b949e',fontsize=9)
                st.image(chart_buf(fig4),use_container_width=True)
        else:
            st.markdown(f"""
            <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;
                 padding:28px;text-align:center;margin:12px 0">
              <div style="font-size:36px;margin-bottom:10px">🤖</div>
              <div style="color:#e6edf3;font-size:16px;font-weight:600;margin-bottom:6px">Not enough data yet</div>
              <div style="color:#8b949e;font-size:13px;margin-bottom:16px">
                The AI model needs at least <strong style="color:#58a6ff">5 completed tasks</strong> with
                actual hours logged to train.<br>
                This project currently has <strong style="color:#d29922">{hist_count} qualifying task(s)</strong>.
              </div>
              <div style="display:inline-flex;gap:8px;flex-wrap:wrap;justify-content:center">
                <div style="background:#21262d;border-radius:6px;padding:8px 14px;font-size:12px;color:#8b949e">
                  1️⃣ Create tasks in Backlog
                </div>
                <div style="background:#21262d;border-radius:6px;padding:8px 14px;font-size:12px;color:#8b949e">
                  2️⃣ Log actual hours on completion
                </div>
                <div style="background:#21262d;border-radius:6px;padding:8px 14px;font-size:12px;color:#8b949e">
                  3️⃣ Complete a sprint
                </div>
              </div>
              <div style="color:#8b949e;font-size:11px;margin-top:12px">
                Until then, predictions use a <span style="color:#fbbf24">rule-based heuristic</span> (estimate × priority factor)
              </div>
            </div>""", unsafe_allow_html=True)

        st.divider()
        st.markdown("**🔮 Predict a Task**")
        opts3=member_opts(team)
        with st.form("pf"):
            pc1,pc2=st.columns(2)
            p_sp=pc1.slider("Story Points",1,13,5)
            p_eh=pc1.number_input("Your Estimated Hours",1.0,80.0,10.0)
            p_pr=pc2.selectbox("Priority",["Low","Medium","High","Critical"],index=2)
            p_mb=pc2.selectbox("Assignee",list(opts3.keys()),format_func=lambda x:opts3[x])
            p_cp=pc2.slider("Sprint Planned Points",20,80,40)
            if st.form_submit_button("🔮 Predict",type="primary"):
                vel4=14.0
                if p_mb and not team.empty:
                    row4=team[team["id"]==p_mb]
                    if not row4.empty: vel4=float(row4["velocity_avg"].values[0])
                pred5=proj_predictor.predict(p_sp,p_eh,p_pr,vel4,p_cp)
                diff5=pred5-p_eh
                r1,r2,r3=st.columns(3)
                r1.metric("AI Predicted",f"{pred5}h")
                r2.metric("Your Estimate",f"{p_eh}h")
                r3.metric("Variance",f"{diff5:+.1f}h",delta_color="inverse" if diff5>0 else "normal")
                mode = "🧠 ML Model" if proj_predictor.trained else "📐 Heuristic"
                st.info(f"Prediction mode: **{mode}**  ·  Risk: {'🔴 High' if diff5>p_eh*0.3 else '🟡 Medium' if diff5>0 else '🟢 Low'}")

    with tab3:
        st.subheader("📈 Velocity Forecast")
        mets5=load_metrics(proj_id)
        if mets5.empty: st.info("No completed sprints yet.")
        else:
            vl5=mets5["velocity"].tolist(); fc5=vel_fc.forecast(vl5)
            v1,v2,v3=st.columns(3)
            v1.metric("Forecast",f"{fc5['forecast']} pts"); v2.metric("Trend",fc5["trend"].capitalize()); v3.metric("Confidence",f"{fc5['confidence']*100:.0f}%")
            fig5,ax5=plt.subplots(figsize=(8,3),facecolor='none')
            x=range(len(vl5)); ax5.bar(x,mets5["planned_points"],color='#21262d',label='Planned',width=0.4,align='edge')
            ax5.bar([i-.4 for i in x],vl5,color='#58a6ff',label='Actual',width=0.4,align='edge')
            ax5.axhline(fc5["forecast"],color='#3fb950',linestyle='--',linewidth=1.5,label=f'Forecast {fc5["forecast"]}')
            ax5.set_xticks(x); ax5.set_xticklabels(mets5["sprint_name"],color='#8b949e',fontsize=9)
            ax5.set_facecolor('#0d1117'); fig5.patch.set_alpha(0); ax5.tick_params(colors='#8b949e'); ax5.spines[:].set_color('#21262d')
            ax5.legend(facecolor='#161b22',edgecolor='#30363d',labelcolor='#8b949e',fontsize=9)
            st.image(chart_buf(fig5),use_container_width=True)

    with tab4:
        st.subheader("🔍 Risk Analyzer")
        if not act: st.warning("No active sprint.")
        else:
            tdf6=load_tasks(sprint_id=act["id"]); tasks6=tdf6.to_dict("records")
            sr6=risk_det.assess_sprint_risk(act,tasks6)
            rc6={"low":"#3fb950","medium":"#d29922","high":"#f85149"}[sr6["level"]]
            st.markdown(f'<div style="background:{rc6}15;border:1px solid {rc6}40;border-radius:8px;padding:14px;margin-bottom:14px">'
                        f'<span style="color:{rc6};font-size:18px;font-weight:700">Sprint Risk: {sr6["level"].upper()}</span>'
                        f'<span style="color:#8b949e;font-size:13px"> (score {sr6["score"]})</span>'
                        f'{"".join(f"<br><span style=color:#8b949e;font-size:12px>⚠️ {r}</span>" for r in sr6["reasons"])}'
                        f'</div>',unsafe_allow_html=True)
            rrows=[]
            for t in tasks6:
                tr7=risk_det.assess_task_risk(t,t.get("velocity_avg",12),7)
                rrows.append({"Task":t["title"],"Assignee":t.get("assignee_name","—"),"Priority":t["priority"],"Status":t["status"],"Risk":tr7["level"].upper(),"Score":tr7["score"],"Reason":tr7["reasons"][0] if tr7["reasons"] else "—"})
            if rrows: st.dataframe(pd.DataFrame(rrows).sort_values("Score",ascending=False),use_container_width=True,hide_index=True)

    with tab5:
        st.subheader("💡 Recommendations")
        if not act: st.info("No active sprint.")
        else:
            tdf7=load_tasks(sprint_id=act["id"]); tasks7=tdf7.to_dict("records")
            # ADD THIS BELOW EXISTING CODE
            rb_insights = generate_insights(tasks7)
            rb_blockers, rb_warnings = detect_blockers(tasks7)
            st.markdown("**Rule-Based Insights**")
            for msg in rb_insights:
                st.markdown(f'<div class="rc rc-info">💡 {msg}</div>', unsafe_allow_html=True)
            if rb_warnings:
                st.markdown("**Blocker Detection Warnings**")
                for warn in rb_warnings:
                    st.markdown(f'<div class="rc rc-warn">⚠️ {warn}</div>', unsafe_allow_html=True)

            mets6=load_metrics(proj_id); vl6=mets6["velocity"].tolist() if not mets6.empty else [30,35,38,40]
            sr7=risk_det.assess_sprint_risk(act,tasks7); vfc7=vel_fc.forecast(vl6)
            recs7=rec_eng.generate(sr7,tasks7,vfc7,team.to_dict("records"))
            rc_map2={"warning":"rc-warn","caution":"rc-caut","action":"rc-act","info":"rc-info","success":"rc-ok"}
            for r in recs7:
                st.markdown(f'<div class="rc {rc_map2.get(r["type"],"rc-info")}"><strong style="color:#e6edf3">{r["icon"]} {r["title"]}</strong><br><span style="color:#8b949e">{r["body"]}</span></div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  📄 REPORTS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Reports":
    st.markdown('<div class="page-wrap">', unsafe_allow_html=True)
    sdf7=load_sprints(pid=proj_id)
    if sdf7.empty: st.info("No sprints yet."); st.markdown('</div>',unsafe_allow_html=True); st.stop()

    sel7=st.selectbox("Select Sprint",sdf7["name"].tolist())
    srow7=sdf7[sdf7["name"]==sel7].iloc[0]; sid7=int(srow7["id"])
    tdf7=load_tasks(sprint_id=sid7); tasks7=tdf7.to_dict("records")
    hlth7=compute_sprint_health(tasks7,srow7.to_dict()); sr7b=risk_det.assess_sprint_risk(srow7.to_dict(),tasks7)
    pp7=int(srow7.get("planned_points",0)); cp7=int(srow7.get("completed_points",0))
    gc7={"A":"#3fb950","B":"#d29922","C":"#f0883e","D":"#f85149","F":"#f85149"}.get(hlth7["grade"],"#8b949e")
    rc7={"low":"#3fb950","medium":"#d29922","high":"#f85149"}[sr7b["level"]]

    stats=[("Story Points",f"{cp7}/{pp7}","#e6edf3"),("Health Score",f"{hlth7['score']}",gc7),
           ("Risk",sr7b["level"].upper(),rc7),("Tasks",len(tasks7),"#e6edf3"),
           ("Done",sum(1 for t in tasks7 if t["status"]=="Done"),"#3fb950"),
           ("Blocked",sum(1 for t in tasks7 if t["status"]=="Blocked"),"#f85149")]
    st.markdown(f"""
    <div class="card" style="margin-bottom:16px">
      <div style="font-size:18px;font-weight:700;color:#e6edf3;margin-bottom:4px">{sel7}</div>
      <div style="color:#8b949e;font-size:13px">📅 {srow7.get('start_date','—')} → {srow7.get('end_date','—')} · {srow7.get('goal') or '—'}</div>
      <div style="display:flex;gap:10px;margin-top:14px;flex-wrap:wrap">
        {''.join(f'<div style="background:#21262d;border-radius:6px;padding:10px 16px;text-align:center;min-width:80px"><div style="color:{c};font-size:20px;font-weight:700">{v}</div><div style="color:#8b949e;font-size:10px">{l}</div></div>' for l,v,c in stats)}
      </div>
    </div>""", unsafe_allow_html=True)

    r1,r2=st.columns(2)
    with r1:
        st.markdown("**🔍 Risk Factors**")
        if sr7b["reasons"]:
            for r in sr7b["reasons"]: st.markdown(f'<div class="rc rc-warn">⚠️ {r}</div>',unsafe_allow_html=True)
        else: st.markdown('<div class="rc rc-ok">✅ No major risks</div>',unsafe_allow_html=True)

        st.markdown("**🤖 Health Breakdown**")
        for comp,score in hlth7["breakdown"].items():
            maxs={"Completion Rate":40,"No Blockers":20,"Velocity Match":25,"Critical Tasks":15}.get(comp,10)
            pct8=score/maxs*100; col8="#3fb950" if pct8>=70 else "#d29922" if pct8>=40 else "#f85149"
            st.markdown(f"""
            <div style="margin-bottom:9px">
              <div style="display:flex;justify-content:space-between;margin-bottom:2px">
                <span style="color:#c9d1d9;font-size:12px">{comp}</span>
                <span style="color:{col8};font-size:12px;font-weight:600">{score}/{maxs}</span>
              </div>
              <div style="background:#21262d;border-radius:3px;height:5px">
                <div style="width:{pct8:.0f}%;background:{col8};height:5px;border-radius:3px"></div>
              </div>
            </div>""", unsafe_allow_html=True)
    with r2:
        st.markdown("**📊 Status Distribution**")
        if tasks7:
            st.dataframe(pd.DataFrame([{"Status":"Done","Count":sum(1 for t in tasks7 if t["status"]=="Done")},{"Status":"In Progress","Count":sum(1 for t in tasks7 if t["status"]=="In Progress")},{"Status":"Todo","Count":sum(1 for t in tasks7 if t["status"]=="Todo")},{"Status":"Blocked","Count":sum(1 for t in tasks7 if t["status"]=="Blocked")}]),use_container_width=True,hide_index=True)

    if not tdf7.empty:
        st.divider(); st.markdown("**All Tasks**")
        sc4=["title","assignee_name","priority","status","story_points","estimated_hours","actual_hours"]
        st.dataframe(tdf7[[c for c in sc4 if c in tdf7.columns]].fillna("—"),use_container_width=True,hide_index=True)
    st.caption("*Auto-generated · AI Sprint Manager · CVR College IOMP Batch 19*")
    st.markdown('</div>',unsafe_allow_html=True)