"""
auth.py
Supabase authentication helpers for Streamlit.
"""
import os
import streamlit as st
from supabase import create_client
from dotenv import load_dotenv

# ADD THIS BELOW EXISTING CODE
load_dotenv()


def _get_supabase_client():
    # ADD THIS BELOW EXISTING CODE
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_ANON_KEY", "")

    if not url and "SUPABASE_URL" in st.secrets:
        url = st.secrets["SUPABASE_URL"]
    if not key and "SUPABASE_ANON_KEY" in st.secrets:
        key = st.secrets["SUPABASE_ANON_KEY"]

    if not url or not key:
        return None, "Missing Supabase credentials. Set SUPABASE_URL and SUPABASE_ANON_KEY."
    if str(key).startswith("http"):
        return None, "SUPABASE_ANON_KEY looks invalid (it should be a long API key, not a URL)."

    try:
        return create_client(url, key), ""
    except Exception as exc:
        return None, f"Supabase client init failed: {exc}"

def _format_auth_error(exc, prefix="Operation failed"):
    err = str(exc)
    if "getaddrinfo" in err or "connection" in err.lower() or "timeout" in err.lower() or "failed to establish" in err.lower():
        return "⚠️ Network Connection Error: Unable to reach the Supabase server. Please check your internet connection and try again."
    if "Email not confirmed" in err or "email not confirmed" in err:
        return (
            f"{prefix}: email not confirmed. Please verify your email first, "
            "or disable email confirmation in Supabase Auth settings for local development."
        )
    return f"{prefix}: {err}"


def signup_user(username, password, role="Member"):
    # ADD THIS BELOW EXISTING CODE
    username = (username or "").strip()
    password = (password or "").strip()
    role = role if role in ("Manager", "Member") else "Member"

    if not username or not password:
        return False, "Username and password are required."
    if "@" not in username:
        return False, "For Supabase auth, Username must be a valid email address."

    client, err = _get_supabase_client()
    if not client:
        return False, err

    try:
        client.auth.sign_up(
            {
                "email": username,
                "password": password,
                "options": {"data": {"role": role, "display_name": username}},
            }
        )
        return True, "Signup successful. Please login."
    except Exception as exc:
        return False, _format_auth_error(exc, "Signup failed")


def login_user(username, password):
    # ADD THIS BELOW EXISTING CODE
    username = (username or "").strip()
    password = (password or "").strip()
    if not username or not password:
        return False, "Username and password are required."

    client, err = _get_supabase_client()
    if not client:
        return False, err

    try:
        resp = client.auth.sign_in_with_password({"email": username, "password": password})
    except Exception as exc:
        return False, _format_auth_error(exc, "Login failed")

    user = getattr(resp, "user", None)
    if not user:
        return False, "Invalid username or password."

    user_meta = getattr(user, "user_metadata", {}) or {}
    role = user_meta.get("role", "Member")

    full_name = user_meta.get("full_name") or user_meta.get("display_name")
    st.session_state["user"] = user.email or username
    st.session_state["user_name"] = full_name
    st.session_state["role"] = role if role in ("Manager", "Member") else "Member"
    return True, "Login successful."


def logout_user():
    # ADD THIS BELOW EXISTING CODE
    client, _ = _get_supabase_client()
    if client:
        try:
            client.auth.sign_out()
        except Exception:
            pass
    st.session_state["user"] = None
    st.session_state["user_name"] = None
    st.session_state["role"] = None
    return True
