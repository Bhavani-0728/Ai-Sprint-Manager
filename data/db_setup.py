"""
db_setup.py — Creates and seeds the Supabase PostgreSQL database for AI Sprint Manager
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_conn():
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise ValueError("Missing SUPABASE_DB_URL environment variable in .env file.")
    try:
        return psycopg2.connect(db_url)
    except Exception as e:
        raise ConnectionError(f"Failed to connect to Supabase PostgreSQL: {e}")


def create_tables(conn):
    cur = conn.cursor()
    
    # 1. Projects table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        description TEXT,
        created_by VARCHAR(255),
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Team Members table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS team_members (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        role VARCHAR(255),
        velocity_avg REAL DEFAULT 10.0,
        project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
        avatar_color VARCHAR(50) DEFAULT '#3b82f6',
        email VARCHAR(255)
    );
    """)

    # 3. Sprints table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sprints (
        id SERIAL PRIMARY KEY,
        project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
        name VARCHAR(255) NOT NULL,
        goal TEXT,
        start_date VARCHAR(50),
        end_date VARCHAR(50),
        status VARCHAR(50) DEFAULT 'Planning',
        planned_points INTEGER DEFAULT 0,
        completed_points INTEGER DEFAULT 0
    );
    """)

    # 4. Tasks table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id SERIAL PRIMARY KEY,
        sprint_id INTEGER REFERENCES sprints(id) ON DELETE SET NULL,
        project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
        title VARCHAR(255) NOT NULL,
        description TEXT,
        assignee_id INTEGER REFERENCES team_members(id) ON DELETE SET NULL,
        priority VARCHAR(50) DEFAULT 'Medium',
        status VARCHAR(50) DEFAULT 'Todo',
        issue_type VARCHAR(50) DEFAULT 'Task',
        story_points INTEGER DEFAULT 1,
        estimated_hours REAL,
        actual_hours REAL,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        tags VARCHAR(255),
        blocker_note TEXT,
        due_date VARCHAR(50)
    );
    """)

    # 5. Sprint Metrics table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sprint_metrics (
        id SERIAL PRIMARY KEY,
        sprint_id INTEGER UNIQUE REFERENCES sprints(id) ON DELETE CASCADE,
        velocity REAL,
        completion_rate REAL,
        avg_cycle_time REAL,
        blockers_count INTEGER DEFAULT 0,
        on_time_tasks INTEGER DEFAULT 0,
        late_tasks INTEGER DEFAULT 0
    );
    """)

    # 6. Activity Log table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS activity_log (
        id SERIAL PRIMARY KEY,
        project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
        sprint_id INTEGER REFERENCES sprints(id) ON DELETE SET NULL,
        task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
        task_title VARCHAR(255),
        actor VARCHAR(255) DEFAULT 'System',
        action VARCHAR(255),
        field_changed VARCHAR(255),
        old_value TEXT,
        new_value TEXT,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 7. Member Comments table (NEW progress logs)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS member_comments (
        id SERIAL PRIMARY KEY,
        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        member_id INTEGER NOT NULL REFERENCES team_members(id) ON DELETE CASCADE,
        sprint_id INTEGER REFERENCES sprints(id) ON DELETE SET NULL,
        task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
        comment_text TEXT NOT NULL CHECK (char_length(trim(comment_text)) > 0),
        hours_logged NUMERIC(5, 2) DEFAULT 0.0 CHECK (hours_logged >= 0.0 AND hours_logged <= 24.0),
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Indexes for performance
    cur.execute("CREATE INDEX IF NOT EXISTS idx_member_comments_proj_memb ON member_comments (project_id, member_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_member_comments_sprint ON member_comments (sprint_id);")
    
    # Mandatory performance/scalability indexes
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_sprint ON tasks(sprint_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assignee_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_team_project ON team_members(project_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sprints_project ON sprints(project_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_activity_project ON activity_log(project_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_metrics_sprint ON sprint_metrics(sprint_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_team_email_lower ON team_members (LOWER(email));")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_project_sprint ON tasks(project_id, sprint_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_project_assignee ON tasks(project_id, assignee_id);")
    
    conn.commit()

    # ── Row Level Security (RLS) for member_comments ──────────────────────────
    # Supabase flags any public table without RLS as a security warning.
    # Enable RLS and grant full CRUD to authenticated users (access scoping is
    # handled at the application layer via project_id / member_id filtering).
    try:
        cur.execute("ALTER TABLE member_comments ENABLE ROW LEVEL SECURITY;")

        for policy in [
            "allow_all_authenticated_select_member_comments",
            "allow_all_authenticated_insert_member_comments",
            "allow_all_authenticated_update_member_comments",
            "allow_all_authenticated_delete_member_comments",
        ]:
            cur.execute(f"DROP POLICY IF EXISTS {policy} ON member_comments;")

        cur.execute("""
            CREATE POLICY allow_all_authenticated_select_member_comments
            ON member_comments FOR SELECT TO authenticated USING (true);
        """)
        cur.execute("""
            CREATE POLICY allow_all_authenticated_insert_member_comments
            ON member_comments FOR INSERT TO authenticated WITH CHECK (true);
        """)
        cur.execute("""
            CREATE POLICY allow_all_authenticated_update_member_comments
            ON member_comments FOR UPDATE TO authenticated USING (true) WITH CHECK (true);
        """)
        cur.execute("""
            CREATE POLICY allow_all_authenticated_delete_member_comments
            ON member_comments FOR DELETE TO authenticated USING (true);
        """)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"RLS setup warning for member_comments: {e}")

    # Dynamic migrations for legacy table columns (in case tables existed prior to mail/creator features)
    try:
        cur.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS created_by VARCHAR(255)")
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Migration warning projects.created_by: {e}")

    try:
        cur.execute("ALTER TABLE team_members ADD COLUMN IF NOT EXISTS email VARCHAR(255)")
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Migration warning team_members.email: {e}")

    cur.close()


def log_activity(project_id, actor, action, task_title="", field_changed="",
                 old_value="", new_value="", task_id=None, sprint_id=None):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""INSERT INTO activity_log
                        (project_id,sprint_id,task_id,task_title,actor,action,field_changed,old_value,new_value)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                     (project_id, sprint_id, task_id, task_title,
                      actor, action, field_changed, old_value, new_value))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Activity logging failed: {e}")


def seed_data(conn):
    # Seeding disabled as requested by the user for a clean environment.
    return


if __name__ == "__main__":
    try:
        conn = get_conn()
        create_tables(conn)
        seed_data(conn)
        conn.close()
        print("Database structure verified/updated successfully.")
    except Exception as exc:
        print("Database setup failed:", exc)