"""
email_helper.py
Automated email notification helper for SprintAI.
Uses Gmail SMTP with App Password (synchronous with timeout).
Fails silently so it never crashes the Streamlit app.
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

def _get_secret(key: str, default: str = "") -> str:
    """Read a secret from environment variables first, then st.secrets as fallback."""
    val = os.getenv(key, "")
    if val:
        return val
    # Fallback: try Streamlit secrets (works on Streamlit Cloud)
    try:
        import streamlit as st
        return st.secrets.get(key, default)
    except Exception:
        return default

SMTP_EMAIL    = _get_secret("SMTP_EMAIL")
SMTP_PASSWORD = _get_secret("SMTP_PASSWORD")
SMTP_HOST     = "smtp.gmail.com"
SMTP_PORT     = 587
SMTP_TIMEOUT  = 10   # seconds — keeps UI responsive


def _build_html_email(subject, body_html, to_email):
    """Build a MIME multipart email with no-reply headers."""
    msg = MIMEMultipart("alternative")
    msg["From"]    = f"SprintAI Notifications <{SMTP_EMAIL}>"
    msg["To"]      = to_email
    msg["Subject"] = subject
    msg["Reply-To"] = "no-reply@sprintai.dev"
    msg["X-Auto-Response-Suppress"] = "All"

    full_html = f"""
    <html>
    <body style="margin:0;padding:0;background:#0d1117;font-family:'Segoe UI',Arial,sans-serif;">
      <div style="max-width:600px;margin:20px auto;background:#161b22;border:1px solid #30363d;border-radius:12px;overflow:hidden;">
        <div style="background:linear-gradient(135deg,#2563eb,#7c3aed);padding:20px 24px;">
          <div style="display:flex;align-items:center;gap:10px;">
            <span style="font-size:24px;">⚡</span>
            <span style="color:#ffffff;font-size:20px;font-weight:700;letter-spacing:-0.3px;">SprintAI</span>
          </div>
          <div style="color:rgba(255,255,255,0.8);font-size:12px;margin-top:4px;">AI-Powered Agile Manager</div>
        </div>
        <div style="padding:24px;">
          {body_html}
        </div>
        <div style="background:#0d1117;padding:16px 24px;border-top:1px solid #30363d;">
          <p style="color:#8b949e;font-size:11px;margin:0;text-align:center;">
            This is an automated notification from SprintAI. Please do not reply to this email.
          </p>
        </div>
      </div>
    </body>
    </html>
    """
    msg.attach(MIMEText(full_html, "html"))
    return msg


def _send_email(to_email, subject, body_html):
    """
    Send email synchronously via Gmail SMTP.
    Fails silently — prints error to console but never raises.
    """
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print("[SprintAI Email] SMTP credentials not configured. Skipping.")
        return
    if not to_email or not to_email.strip():
        print("[SprintAI Email] No recipient email. Skipping.")
        return

    try:
        msg = _build_html_email(subject, body_html, to_email.strip())
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email.strip(), msg.as_string())
        print(f"[SprintAI Email] ✅ Sent '{subject}' → {to_email}")
    except smtplib.SMTPException as e:
        print(f"[SprintAI Email] ❌ SMTP error sending to {to_email}: {e}")
    except OSError as e:
        print(f"[SprintAI Email] ❌ Network error sending to {to_email}: {e}")
    except Exception as e:
        print(f"[SprintAI Email] ❌ Unexpected error sending to {to_email}: {e}")


# ── Public API ───────────────────────────────────────────────────────────────

def notify_manager(manager_email, subject, body_html):
    """Send a notification email to the project manager."""
    _send_email(manager_email, subject, body_html)


def notify_member(member_email, subject, body_html):
    """Send a notification email to a team member."""
    _send_email(member_email, subject, body_html)


# ── Email body templates ─────────────────────────────────────────────────────

def build_progress_log_email(member_name, sprint_name, task_title, hours_logged, comment, timestamp):
    """HTML body: member submitted a daily progress log → sent to manager."""
    task_row  = (f'<tr><td style="color:#8b949e;padding:8px 12px;">Task</td>'
                 f'<td style="color:#e6edf3;padding:8px 12px;font-weight:500;">{task_title}</td></tr>') if task_title else ""
    hours_row = (f'<tr><td style="color:#8b949e;padding:8px 12px;">Hours Logged</td>'
                 f'<td style="color:#3fb950;padding:8px 12px;font-weight:600;">{hours_logged}h</td></tr>') if hours_logged and hours_logged > 0 else ""

    return f"""
    <h2 style="color:#e6edf3;font-size:18px;margin:0 0 16px;">📝 Daily Progress Update</h2>
    <table style="width:100%;border-collapse:collapse;background:#0d1117;border-radius:8px;overflow:hidden;border:1px solid #30363d;">
      <tr><td style="color:#8b949e;padding:8px 12px;">Member</td>
          <td style="color:#58a6ff;padding:8px 12px;font-weight:600;">{member_name}</td></tr>
      <tr style="background:#161b2280;">
          <td style="color:#8b949e;padding:8px 12px;">Sprint</td>
          <td style="color:#e6edf3;padding:8px 12px;">{sprint_name or '— Backlog —'}</td></tr>
      {task_row}
      {hours_row}
      <tr style="background:#161b2280;">
          <td style="color:#8b949e;padding:8px 12px;">Timestamp</td>
          <td style="color:#8b949e;padding:8px 12px;">{timestamp}</td></tr>
    </table>
    <div style="margin-top:16px;padding:14px;background:#0d1117;border:1px solid #30363d;
                border-radius:8px;border-left:3px solid #58a6ff;">
      <div style="color:#8b949e;font-size:11px;margin-bottom:6px;text-transform:uppercase;
                  letter-spacing:0.5px;">Progress Comment</div>
      <div style="color:#e6edf3;font-size:14px;line-height:1.5;">{comment}</div>
    </div>
    """


def build_task_assignment_email(task_title, description, priority, story_points,
                                estimated_hours, sprint_name, project_name, assigned_by="Manager"):
    """HTML body: new task assigned to member → sent to that member."""
    pri_colors = {"Critical": "#f85149", "High": "#d29922", "Medium": "#58a6ff", "Low": "#8b949e"}
    pri_color  = pri_colors.get(priority, "#58a6ff")
    desc_text  = description or "No description provided."

    return f"""
    <h2 style="color:#e6edf3;font-size:18px;margin:0 0 6px;">🎯 New Task Assigned to You</h2>
    <p style="color:#8b949e;font-size:13px;margin:0 0 20px;">
      You have been assigned a new task in <strong style="color:#58a6ff;">{project_name}</strong>
    </p>
    <div style="background:#0d1117;border:1px solid #30363d;border-radius:8px;
                overflow:hidden;border-left:4px solid {pri_color};">
      <div style="padding:16px;">
        <div style="color:#e6edf3;font-size:16px;font-weight:600;margin-bottom:8px;">{task_title}</div>
        <div style="color:#8b949e;font-size:13px;margin-bottom:16px;line-height:1.5;">{desc_text}</div>
        <table style="width:100%;border-collapse:collapse;">
          <tr>
            <td style="padding:6px 0;">
              <span style="color:#8b949e;font-size:12px;">Priority</span><br>
              <span style="color:{pri_color};font-weight:600;">{priority}</span>
            </td>
            <td style="padding:6px 0;">
              <span style="color:#8b949e;font-size:12px;">Story Points</span><br>
              <span style="color:#e6edf3;font-weight:600;">{story_points} pt</span>
            </td>
            <td style="padding:6px 0;">
              <span style="color:#8b949e;font-size:12px;">Estimated Hours</span><br>
              <span style="color:#e6edf3;font-weight:600;">{estimated_hours}h</span>
            </td>
          </tr>
          <tr>
            <td style="padding:6px 0;">
              <span style="color:#8b949e;font-size:12px;">Sprint</span><br>
              <span style="color:#e6edf3;">{sprint_name or '— Backlog —'}</span>
            </td>
            <td style="padding:6px 0;" colspan="2">
              <span style="color:#8b949e;font-size:12px;">Assigned By</span><br>
              <span style="color:#e6edf3;">{assigned_by}</span>
            </td>
          </tr>
        </table>
      </div>
    </div>
    <p style="color:#8b949e;font-size:12px;margin-top:16px;">
      Log in to SprintAI to view and manage this task.
    </p>
    """


def build_task_reassignment_email(task_title, priority, status, sprint_name,
                                   estimated_hours, project_name):
    """HTML body: task re-assigned → sent to new assignee."""
    pri_colors = {"Critical": "#f85149", "High": "#d29922", "Medium": "#58a6ff", "Low": "#8b949e"}
    pri_color  = pri_colors.get(priority, "#58a6ff")

    return f"""
    <h2 style="color:#e6edf3;font-size:18px;margin:0 0 6px;">🔄 Task Assigned to You</h2>
    <p style="color:#8b949e;font-size:13px;margin:0 0 20px;">
      A task in <strong style="color:#58a6ff;">{project_name}</strong> has been assigned to you.
    </p>
    <div style="background:#0d1117;border:1px solid #30363d;border-radius:8px;
                overflow:hidden;border-left:4px solid {pri_color};padding:16px;">
      <div style="color:#e6edf3;font-size:16px;font-weight:600;margin-bottom:12px;">{task_title}</div>
      <table style="width:100%;border-collapse:collapse;">
        <tr>
          <td style="padding:6px 0;">
            <span style="color:#8b949e;font-size:12px;">Priority</span><br>
            <span style="color:{pri_color};font-weight:600;">{priority}</span>
          </td>
          <td style="padding:6px 0;">
            <span style="color:#8b949e;font-size:12px;">Status</span><br>
            <span style="color:#e6edf3;">{status}</span>
          </td>
          <td style="padding:6px 0;">
            <span style="color:#8b949e;font-size:12px;">Est. Hours</span><br>
            <span style="color:#e6edf3;">{estimated_hours}h</span>
          </td>
        </tr>
        <tr>
          <td style="padding:6px 0;" colspan="3">
            <span style="color:#8b949e;font-size:12px;">Sprint</span><br>
            <span style="color:#e6edf3;">{sprint_name or '— Backlog —'}</span>
          </td>
        </tr>
      </table>
    </div>
    <p style="color:#8b949e;font-size:12px;margin-top:16px;">
      Log in to SprintAI to view and manage this task.
    </p>
    """


def build_task_status_email(member_name, task_title, old_status, new_status,
                             sprint_name, project_name, blocker_note=""):
    """HTML body: member updated task status → sent to manager."""
    status_colors = {
        "Todo": "#8b949e", "In Progress": "#2563eb",
        "Done": "#3fb950", "Blocked": "#f85149"
    }
    new_color = status_colors.get(new_status, "#8b949e")
    old_color = status_colors.get(old_status, "#8b949e")
    blocker_row = (
        f'<tr style="background:#1a0b0b;"><td style="color:#f85149;padding:8px 12px;">Blocker Note</td>'
        f'<td style="color:#f85149;padding:8px 12px;font-weight:500;">{blocker_note}</td></tr>'
    ) if blocker_note else ""

    return f"""
    <h2 style="color:#e6edf3;font-size:18px;margin:0 0 16px;">🔄 Task Status Updated</h2>
    <table style="width:100%;border-collapse:collapse;background:#0d1117;border-radius:8px;
                  overflow:hidden;border:1px solid #30363d;">
      <tr><td style="color:#8b949e;padding:8px 12px;">Member</td>
          <td style="color:#58a6ff;padding:8px 12px;font-weight:600;">{member_name}</td></tr>
      <tr style="background:#161b2280;">
          <td style="color:#8b949e;padding:8px 12px;">Task</td>
          <td style="color:#e6edf3;padding:8px 12px;font-weight:500;">{task_title}</td></tr>
      <tr><td style="color:#8b949e;padding:8px 12px;">Sprint</td>
          <td style="color:#e6edf3;padding:8px 12px;">{sprint_name or "— Backlog —"}</td></tr>
      <tr style="background:#161b2280;">
          <td style="color:#8b949e;padding:8px 12px;">Status Change</td>
          <td style="padding:8px 12px;">
            <span style="color:{old_color};font-weight:500;">{old_status}</span>
            <span style="color:#8b949e;margin:0 8px;">→</span>
            <span style="color:{new_color};font-weight:700;">{new_status}</span>
          </td></tr>
      {blocker_row}
    </table>
    <p style="color:#8b949e;font-size:12px;margin-top:16px;">
      Log in to SprintAI to view the full sprint board.
    </p>
    """


def build_team_welcome_email(member_name, project_name, project_description,
                              manager_email, role):
    """HTML body: member added to a project → sent to that member."""
    desc_text = project_description or "No description provided."

    return f"""
    <h2 style="color:#e6edf3;font-size:18px;margin:0 0 6px;">👋 Welcome to the Team!</h2>
    <p style="color:#8b949e;font-size:13px;margin:0 0 20px;">
      Hi <strong style="color:#58a6ff;">{member_name}</strong>,
      you have been added to a project on SprintAI.
    </p>
    <div style="background:#0d1117;border:1px solid #30363d;border-radius:8px;
                overflow:hidden;border-left:4px solid #2563eb;">
      <div style="padding:16px;">
        <div style="color:#e6edf3;font-size:18px;font-weight:700;margin-bottom:8px;">
          📁 {project_name}
        </div>
        <div style="color:#8b949e;font-size:13px;margin-bottom:16px;line-height:1.5;">
          {desc_text}
        </div>
        <table style="width:100%;border-collapse:collapse;">
          <tr>
            <td style="padding:6px 0;">
              <span style="color:#8b949e;font-size:12px;">Your Role</span><br>
              <span style="color:#e6edf3;font-weight:600;">{role}</span>
            </td>
            <td style="padding:6px 0;">
              <span style="color:#8b949e;font-size:12px;">Project Manager</span><br>
              <span style="color:#e6edf3;">{manager_email}</span>
            </td>
          </tr>
        </table>
      </div>
    </div>
    <p style="color:#8b949e;font-size:12px;margin-top:16px;">
      Log in to SprintAI with your registered email to view tasks and submit daily progress logs.
    </p>
    """
