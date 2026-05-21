import re
import streamlit as st
import pandas as pd
from socket_manager import get_healthy_db, send_remote_command

st.set_page_config(page_title="Parental Control Admin", layout="wide", page_icon="🛡️")

def apply_theme():
    st.markdown("""
    <style>
    /* Modern Green Theme */
    .stApp {
        background-color: #f4f7f6;
    }
    .stButton>button {
        background-color: #2e7d32;
        color: white;
        border-radius: 8px;
        border: none;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #1b5e20;
        color: white;
        border-color: #1b5e20;
    }
    .status-allowed {
        background-color: #e8f5e9;
        color: #2e7d32;
        padding: 6px 12px;
        border-radius: 16px;
        font-weight: 600;
        font-size: 0.9em;
        display: inline-block;
    }
    .status-locked {
        background-color: #ffebee;
        color: #c62828;
        padding: 6px 12px;
        border-radius: 16px;
        font-weight: 600;
        font-size: 0.9em;
        display: inline-block;
    }
    </style>
    """, unsafe_allow_html=True)

apply_theme()

# --- INITIALIZATION ---
db = get_healthy_db()

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "parent_email" not in st.session_state:
    st.session_state["parent_email"] = ""
if "show_registration" not in st.session_state:
    st.session_state["show_registration"] = False


# ═══════════════════════════════════════════════════════════════════
#  PASSWORD VALIDATION HELPERS
# ═══════════════════════════════════════════════════════════════════

def validate_email(email: str) -> str | None:
    """Return an error message if email is invalid, else None."""
    if not email or not email.strip():
        return "Email is required."
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email.strip()):
        return "Please enter a valid email address."
    return None


def validate_password(password: str) -> str | None:
    """Return an error message if password is weak, else None."""
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    if not re.search(r'[A-Z]', password):
        return "Password must contain at least one uppercase letter."
    if not re.search(r'[0-9]', password):
        return "Password must contain at least one digit."
    return None


# ═══════════════════════════════════════════════════════════════════
#  REGISTRATION VIEW
# ═══════════════════════════════════════════════════════════════════

def registration_view():
    st.title("🛡️ Admin Registration")
    st.caption("Create a new parent account to manage your family.")

    with st.form("registration_form"):
        email = st.text_input("Parent Email", placeholder="parent@example.com")
        password = st.text_input("Password", type="password", help="Min 8 chars, 1 uppercase, 1 digit")
        confirm = st.text_input("Confirm Password", type="password")
        submit = st.form_submit_button("Create Account", type="primary")

        if submit:
            # Validate email
            email_err = validate_email(email)
            if email_err:
                st.error(email_err)
                return

            # Validate password strength
            pwd_err = validate_password(password)
            if pwd_err:
                st.error(pwd_err)
                return

            # Confirm match
            if password != confirm:
                st.error("Passwords do not match.")
                return

            # Attempt registration
            try:
                db.register_parent(email.strip(), password)
                st.success("✅ Account created successfully! You can now log in.")
                st.session_state["show_registration"] = False
                st.rerun()
            except ValueError as ve:
                st.error(str(ve))
            except Exception as e:
                st.error(f"Registration failed: {e}")

    st.divider()
    if st.button("← Back to Login"):
        st.session_state["show_registration"] = False
        st.rerun()


# ═══════════════════════════════════════════════════════════════════
#  LOGIN VIEW
# ═══════════════════════════════════════════════════════════════════

def login_view():
    st.title("🛡️ Admin Dashboard Login")

    with st.form("login_form"):
        email = st.text_input("Parent Email")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")

        if submit:
            try:
                if db.verify_admin(email, password):
                    st.session_state["logged_in"] = True
                    st.session_state["parent_email"] = email
                    st.rerun()
                else:
                    st.error("Invalid email or password.")
            except Exception as e:
                st.error(f"Login error: {e}")

    st.divider()
    if st.button("Don't have an account? Register here"):
        st.session_state["show_registration"] = True
        st.rerun()


# ═══════════════════════════════════════════════════════════════════
#  DASHBOARD VIEW
# ═══════════════════════════════════════════════════════════════════

def dashboard_view():
    st.sidebar.title(f"Welcome, {st.session_state['parent_email']}")
    if st.sidebar.button("Logout"):
        st.session_state["logged_in"] = False
        st.session_state["parent_email"] = ""
        st.rerun()

    st.title("Control Center")

    # ── Activity Visualization ──────────────────────────────────────
    st.header("📊 Activity Monitor")

    try:
        usage_query = """
        SELECT u.name as child_name, ul.app_name, ul.duration, ul.start_time
        FROM usage_logs ul
        JOIN users u ON ul.user_id = u.id
        WHERE DATE(ul.start_time) = CURDATE()
        """
        df_usage = db.get_dataframe_data(usage_query)

        if not df_usage.empty:
            agg_df = df_usage.groupby(['child_name', 'app_name'])['duration'].sum().reset_index()

            st.subheader("Today's App Usage (Minutes)")
            st.bar_chart(data=agg_df, x="app_name", y="duration", color="child_name")

            with st.expander("View Raw Logs"):
                st.dataframe(df_usage, use_container_width=True)
        else:
            st.info("No activity logged today yet.")
    except Exception as e:
        st.error(f"Failed to load activity data: {e}")

    st.divider()

    # ── Rule Management & Remote Commands ───────────────────────────
    st.header("⚙️ Rules & Overrides")

    try:
        children = db.get_users_by_type("child")
    except Exception as e:
        st.error(f"Failed to load children: {e}")
        return

    if not children:
        st.warning("No children found in the database. Please register them first.")
        return

    tabs = st.tabs([child["name"] for child in children])

    for idx, child in enumerate(children):
        with tabs[idx]:
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Manage Rules")
                try:
                    rules_query = "SELECT app_name, allowed_minutes FROM app_rules WHERE user_id = %s"
                    df_rules = db.get_dataframe_data(rules_query, params=(child['id'],))
                    st.dataframe(df_rules, use_container_width=True, hide_index=True)
                except Exception as e:
                    st.error(f"Failed to load rules: {e}")

                with st.form(f"rule_form_{child['id']}"):
                    st.write("Add / Update Rule")
                    app_input = st.text_input("App Name (e.g. mspaint.exe)", key=f"app_{child['id']}")
                    time_input = st.number_input("Allowed Minutes (0 to lock)", min_value=0, value=60, step=15, key=f"time_{child['id']}")
                    if st.form_submit_button("Save Rule"):
                        if not app_input.strip():
                            st.error("Please enter an app name.")
                        else:
                            try:
                                res = send_remote_command("update_rule", {
                                    "user_id": child["id"],
                                    "app": app_input.strip(),
                                    "allowed": time_input
                                })
                                if res and res.get("status") == "success":
                                    st.success(f"Rule updated for {app_input}")
                                    st.rerun()
                                else:
                                    st.error(f"Failed to update rule: {res}")
                            except Exception as e:
                                st.error(f"Command error: {e}")

            with col2:
                st.subheader("⚡ Remote Commands")
                st.info("These commands are sent instantly over the socket protocol.")

                target_app = st.text_input("Target App for Override", key=f"target_{child['id']}", help="Name of the executable.")

                # Add Time Button
                if st.button("➕ Add 30 Minutes", key=f"add_{child['id']}", type="primary"):
                    if not target_app:
                        st.error("Please enter a Target App!")
                    else:
                        try:
                            res = send_remote_command("add_time", {
                                "user_id": child["id"],
                                "app": target_app,
                                "minutes": 30
                            })
                            if res and res.get("status") == "success":
                                st.success(f"Added 30 minutes to {target_app}!")
                            else:
                                st.error(f"Command failed: {res}")
                        except Exception as e:
                            st.error(f"Command error: {e}")

                # Force Unlock Button
                if st.button("🔓 Force Unlock (24h)", key=f"unlock_{child['id']}"):
                    if not target_app:
                        st.error("Please enter a Target App!")
                    else:
                        try:
                            res = send_remote_command("unlock_app", {
                                "user_id": child["id"],
                                "app": target_app
                            })
                            if res and res.get("status") == "success":
                                st.success(f"{target_app} has been unlocked!")
                            else:
                                st.error(f"Command failed: {res}")
                        except Exception as e:
                            st.error(f"Command error: {e}")

                st.divider()
                st.write("**Administrative Controls**")
                # Emergency Unlock Button
                if st.button("🚨 Emergency Unlock (All Apps)", key=f"emer_{child['id']}", help="Instantly closes any active lock screen for this child."):
                    try:
                        res = send_remote_command("emergency_unlock", {
                            "user_id": child["id"]
                        })
                        if res and res.get("status") == "success":
                            st.success("Emergency unlock signal sent!")
                        else:
                            st.error(f"Command failed: {res}")
                    except Exception as e:
                        st.error(f"Command error: {e}")

    st.divider()

    # ── App Blocker (Option C) ──────────────────────────────────────
    st.header("🔒 App Blocker")
    st.caption("Search for known apps or add a custom one. Toggle the lock to set allowed_minutes = 0.")

    if not children:
        return

    blocker_tabs = st.tabs([f"🔒 {child['name']}" for child in children])

    for idx, child in enumerate(children):
        with blocker_tabs[idx]:
            child_id = child["id"]
            search_key = f"blocker_search_{child_id}"

            # ── Fetch known apps from server ──
            known_apps = []
            try:
                res = send_remote_command("get_known_apps", {"user_id": child_id})
                if res and res.get("status") == "success":
                    known_apps = res.get("apps", [])
            except Exception:
                pass

            # Fallback: direct DB query if server unavailable
            if not known_apps:
                try:
                    known_apps = db.get_known_apps(child_id)
                except Exception:
                    known_apps = []

            # ── Fetch current rules to know which are locked ──
            locked_apps = set()
            try:
                rules_query = "SELECT app_name, allowed_minutes FROM app_rules WHERE user_id = %s"
                df_current_rules = db.get_dataframe_data(rules_query, params=(child_id,))
                if not df_current_rules.empty:
                    for _, row in df_current_rules.iterrows():
                        if row["allowed_minutes"] == 0:
                            locked_apps.add(row["app_name"])
            except Exception:
                pass

            # ── Search Bar ──
            search_query = st.text_input(
                "🔍 Search apps...",
                key=search_key,
                placeholder="Type to filter (e.g. 'photo', 'chrome', 'note')"
            )

            # ── Filter apps ──
            if search_query.strip():
                filtered_apps = [
                    app for app in known_apps
                    if search_query.strip().lower() in app.lower()
                ]
            else:
                filtered_apps = known_apps

            # ── Display apps with lock toggles ──
            if filtered_apps:
                st.write(f"**{len(filtered_apps)}** app(s) found:")
                for app_name in filtered_apps:
                    is_locked = app_name in locked_apps
                    col_name, col_status, col_action = st.columns([3, 1, 2])

                    with col_name:
                        st.write(f"📦 `{app_name}`")

                    with col_status:
                        if is_locked:
                            st.markdown('<div class="status-locked">🔴 Locked</div>', unsafe_allow_html=True)
                        else:
                            st.markdown('<div class="status-allowed">🟢 Allowed</div>', unsafe_allow_html=True)

                    with col_action:
                        if is_locked:
                            if st.button("🔓 Unlock", key=f"unlock_blocker_{child_id}_{app_name}"):
                                try:
                                    res = send_remote_command("unlock_app", {
                                        "user_id": child_id,
                                        "app": app_name
                                    })
                                    if res and res.get("status") == "success":
                                        st.success(f"Unlocked {app_name}")
                                        st.rerun()
                                    else:
                                        st.error(f"Failed: {res}")
                                except Exception as e:
                                    st.error(f"Error: {e}")
                        else:
                            if st.button("🔒 Lock", key=f"lock_blocker_{child_id}_{app_name}"):
                                try:
                                    res = send_remote_command("lock_app", {
                                        "user_id": child_id,
                                        "app": app_name
                                    })
                                    if res and res.get("status") == "success":
                                        st.success(f"Locked {app_name} (0 min allowed)")
                                        st.rerun()
                                    else:
                                        st.error(f"Failed: {res}")
                                except Exception as e:
                                    st.error(f"Error: {e}")
            elif search_query.strip():
                st.info(f"No apps matching '{search_query}' found.")
            else:
                st.info("No known apps recorded for this child yet. Use the form below to add one manually.")

            # ── Add Custom App (manual entry) ──
            st.divider()
            with st.form(f"custom_app_form_{child_id}"):
                st.write("**Add Custom App**")
                custom_app = st.text_input("App executable name", key=f"custom_app_{child_id}", placeholder="e.g. game.exe")
                custom_action = st.selectbox("Action", ["Lock (0 minutes)", "Allow (60 minutes)", "Allow (120 minutes)"], key=f"custom_action_{child_id}")
                if st.form_submit_button("Apply"):
                    if not custom_app.strip():
                        st.error("Please enter an app name.")
                    else:
                        minutes_map = {
                            "Lock (0 minutes)": 0,
                            "Allow (60 minutes)": 60,
                            "Allow (120 minutes)": 120,
                        }
                        minutes = minutes_map.get(custom_action, 60)
                        try:
                            cmd = "lock_app" if minutes == 0 else "update_rule"
                            payload = {"user_id": child_id, "app": custom_app.strip()}
                            if cmd == "update_rule":
                                payload["allowed"] = minutes
                            res = send_remote_command(cmd, payload)
                            if res and res.get("status") == "success":
                                st.success(f"{'Locked' if minutes == 0 else 'Allowed'} {custom_app.strip()} ({minutes} min)")
                                st.rerun()
                            else:
                                st.error(f"Failed: {res}")
                        except Exception as e:
                            st.error(f"Error: {e}")


# ═══════════════════════════════════════════════════════════════════
#  MAIN ROUTING LOGIC
# ═══════════════════════════════════════════════════════════════════

if st.session_state["logged_in"]:
    dashboard_view()
elif st.session_state["show_registration"]:
    registration_view()
else:
    login_view()
