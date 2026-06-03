"""
db_setup.py — Creates and seeds the SQLite database for AI Sprint Manager
"""
import sqlite3
import random
from datetime import datetime, timedelta

DB_PATH = "sprint_manager.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def create_tables(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS team_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        role TEXT,
        velocity_avg REAL DEFAULT 10.0,
        project_id INTEGER,
        avatar_color TEXT DEFAULT '#3b82f6',
        FOREIGN KEY (project_id) REFERENCES projects(id)
    );

    CREATE TABLE IF NOT EXISTS sprints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        name TEXT NOT NULL,
        goal TEXT,
        start_date TEXT,
        end_date TEXT,
        status TEXT DEFAULT 'Planning',
        planned_points INTEGER DEFAULT 0,
        completed_points INTEGER DEFAULT 0,
        FOREIGN KEY (project_id) REFERENCES projects(id)
    );

    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sprint_id INTEGER,
        project_id INTEGER,
        title TEXT NOT NULL,
        description TEXT,
        assignee_id INTEGER,
        priority TEXT DEFAULT 'Medium',
        status TEXT DEFAULT 'Todo',
        issue_type TEXT DEFAULT 'Task',
        story_points INTEGER DEFAULT 1,
        estimated_hours REAL,
        actual_hours REAL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        tags TEXT,
        blocker_note TEXT,
        due_date TEXT,
        FOREIGN KEY (sprint_id) REFERENCES sprints(id),
        FOREIGN KEY (assignee_id) REFERENCES team_members(id)
    );

    CREATE TABLE IF NOT EXISTS sprint_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sprint_id INTEGER UNIQUE,
        velocity REAL,
        completion_rate REAL,
        avg_cycle_time REAL,
        blockers_count INTEGER DEFAULT 0,
        on_time_tasks INTEGER DEFAULT 0,
        late_tasks INTEGER DEFAULT 0,
        FOREIGN KEY (sprint_id) REFERENCES sprints(id)
    );

    CREATE TABLE IF NOT EXISTS activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        sprint_id INTEGER,
        task_id INTEGER,
        task_title TEXT,
        actor TEXT DEFAULT 'System',
        action TEXT,
        field_changed TEXT,
        old_value TEXT,
        new_value TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (project_id) REFERENCES projects(id)
    );
    """)
    conn.commit()

def log_activity(project_id, actor, action, task_title="", field_changed="",
                 old_value="", new_value="", task_id=None, sprint_id=None):
    conn = get_conn()
    conn.execute("""INSERT INTO activity_log
                    (project_id,sprint_id,task_id,task_title,actor,action,field_changed,old_value,new_value)
                    VALUES(?,?,?,?,?,?,?,?,?)""",
                 (project_id, sprint_id, task_id, task_title,
                  actor, action, field_changed, old_value, new_value))
    conn.commit()
    conn.close()

def seed_data(conn):
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM projects")
    if c.fetchone()[0] > 0:
        return

    c.execute("INSERT INTO projects(name,description) VALUES(?,?)",
              ("AI Sprint Manager", "CVR College IOMP Project — Batch 19"))
    pid = c.lastrowid

    colors = ['#ec4899','#3b82f6','#10b981','#f59e0b']
    team = [
        ("K. Amulya",        "Frontend Developer",  14.5, colors[0]),
        ("M. Bhavani",       "ML Engineer",          16.0, colors[1]),
        ("B.G.L. Santhoshi", "Backend Developer",    15.0, colors[2]),
        ("Mr. Sudheer",      "Supervisor/QA",        12.0, colors[3]),
    ]
    mids = []
    for name, role, vel, col in team:
        c.execute("INSERT INTO team_members(name,role,velocity_avg,project_id,avatar_color) VALUES(?,?,?,?,?)",
                  (name, role, vel, pid, col))
        mids.append(c.lastrowid)

    sprints_data = [
        ("Sprint 1","Set up base infrastructure","2025-01-06","2025-01-17","Completed",36,30),
        ("Sprint 2","Implement core task management","2025-01-20","2025-01-31","Completed",42,40),
        ("Sprint 3","ML model integration","2025-02-03","2025-02-14","Completed",40,38),
        ("Sprint 4","Dashboard & analytics","2025-02-17","2025-02-28","Completed",44,44),
    ]
    task_templates = [
        ("Set up project repo","High","Story",3,6,5.5),
        ("Design database schema","High","Task",5,10,11),
        ("Build REST API endpoints","Critical","Story",8,16,18),
        ("Implement user auth","High","Task",5,10,9.5),
        ("Write unit tests","Medium","Task",3,6,6.5),
        ("Data preprocessing module","High","Story",5,10,10),
        ("Train ML prediction model","Critical","Story",8,16,17),
        ("Sprint report generator","Medium","Task",3,6,5),
        ("UI dashboard component","High","Story",5,10,12),
        ("Integrate Scikit-learn","High","Task",5,10,10),
        ("Risk detection logic","Critical","Story",8,16,15),
        ("Streamlit frontend pages","High","Task",5,10,9),
    ]
    for i,(sname,goal,sd,ed,stat,pp,cp) in enumerate(sprints_data):
        c.execute("""INSERT INTO sprints(project_id,name,goal,start_date,end_date,status,planned_points,completed_points)
                     VALUES(?,?,?,?,?,?,?,?)""",(pid,sname,goal,sd,ed,stat,pp,cp))
        sid = c.lastrowid
        for j in range(4):
            t = task_templates[(i*3+j)%len(task_templates)]
            title,pri,itype,sp,est,act = t
            status = "Done" if random.random()>0.2 else "In Progress"
            c.execute("""INSERT INTO tasks(sprint_id,project_id,title,assignee_id,priority,status,
                          issue_type,story_points,estimated_hours,actual_hours,tags,updated_at)
                         VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (sid,pid,title,mids[j%len(mids)],pri,status,itype,sp,est,
                       round(act+random.uniform(-1,2),1),"ml,backend",ed))
            c.execute("""INSERT INTO activity_log(project_id,sprint_id,task_title,actor,action,field_changed,new_value)
                         VALUES(?,?,?,?,?,?,?)""",
                      (pid,sid,title,"System","created","status","Todo"))
        dc = round(random.uniform(1.5,3.5),2)
        c.execute("""INSERT INTO sprint_metrics(sprint_id,velocity,completion_rate,avg_cycle_time,blockers_count,on_time_tasks,late_tasks)
                     VALUES(?,?,?,?,?,?,?)""",
                  (sid,cp,round(cp/pp*100,1),dc,random.randint(0,3),random.randint(2,4),random.randint(0,2)))

    # Active Sprint 5
    c.execute("""INSERT INTO sprints(project_id,name,goal,start_date,end_date,status,planned_points,completed_points)
                 VALUES(?,?,?,?,?,?,?,?)""",
              (pid,"Sprint 5","AI recommendations & reporting","2026-03-01","2026-03-14","Active",40,18))
    asid = c.lastrowid
    active_tasks = [
        ("NLP user story parser",        "Critical","Story",8,16,None, 0,"In Progress","nlp,ml",    None),
        ("Recommendation engine",        "High",    "Story",5,10,None, 1,"In Progress","ml",        None),
        ("Automated retrospective",      "High",    "Task", 5,10,None, 2,"Todo",       "reporting", None),
        ("Streamlit UI polish",          "Medium",  "Task", 3, 6, 5.5, 3,"Done",       "ui",        None),
        ("Integration tests",            "High",    "Task", 5,10,None, 0,"Blocked",    "testing",   "Waiting for NLP model"),
        ("Performance benchmarking",     "Low",     "Task", 2, 4,None, 1,"Todo",       "ml",        None),
        ("Deploy on local server",       "High",    "Story",5,10,None, 2,"In Progress","devops",    None),
        ("Sprint 5 demo prep",           "Medium",  "Task", 3, 6,None, 3,"Todo",       "docs",      None),
    ]
    for title,pri,itype,sp,est,act,midx,status,tags,blk in active_tasks:
        c.execute("""INSERT INTO tasks(sprint_id,project_id,title,assignee_id,priority,status,
                      issue_type,story_points,estimated_hours,actual_hours,tags,blocker_note)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (asid,pid,title,mids[midx],pri,status,itype,sp,est,act,tags,blk))
        c.execute("""INSERT INTO activity_log(project_id,sprint_id,task_title,actor,action,field_changed,new_value)
                     VALUES(?,?,?,?,?,?,?)""",
                  (pid,asid,title,["K. Amulya","M. Bhavani","B.G.L. Santhoshi","Mr. Sudheer"][midx],
                   "created","status","Todo"))
    conn.commit()

if __name__ == "__main__":
    conn = get_conn()
    create_tables(conn)
    seed_data(conn)
    conn.close()
    print("Done.")