import re
import streamlit as st
import pandas as pd
from socket_manager import get_healthy_db, send_remote_command

st.set_page_config(page_title="Warden - Parental Control", layout="wide", page_icon="🛡️")

# ═══════════════════════════════════════════════════════════════════
#  PROFESSIONAL BLUE THEME
# ═══════════════════════════════════════════════════════════════════

def apply_theme():
    st.markdown("""
    <style>
    /* ── Professional Blue Theme ────────────────────────────── */

    /* Import Inter font from Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    .stApp {
        background-color: #f0f4f8;
        font-family: 'Inter', sans-serif;
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #003366 0%, #00254d 100%);
    }
    [data-testid="stSidebar"] * {
        color: #e0e7ff !important;
    }

    /* Primary buttons */
    .stButton>button {
        background-color: #005A9C;
        color: white;
        border-radius: 8px;
        border: none;
        font-weight: 600;
        transition: all 0.25s ease;
        font-family: 'Inter', sans-serif;
    }
    .stButton>button:hover {
        background-color: #003d6b;
        color: white;
        border-color: #003d6b;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,90,156,0.3);
    }

    /* Form submit buttons */
    .stFormSubmitButton>button {
        background-color: #005A9C;
        color: white;
        border-radius: 8px;
        border: none;
        font-weight: 600;
    }

    /* Status chips */
    .status-allowed {
        background-color: #dbeafe;
        color: #1e40af;
        padding: 5px 14px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85em;
        display: inline-block;
        letter-spacing: 0.02em;
    }
    .status-locked {
        background-color: #fee2e2;
        color: #991b1b;
        padding: 5px 14px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85em;
        display: inline-block;
        letter-spacing: 0.02em;
    }

    /* Section card-like containers */
    [data-testid="stExpander"] {
        border: 1px solid #cbd5e1;
        border-radius: 10px;
    }

    /* Metric labels */
    [data-testid="stMetricLabel"] {
        color: #334155;
        font-weight: 600;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab"] {
        font-weight: 600;
        color: #334155;
    }
    .stTabs [aria-selected="true"] {
        border-bottom-color: #005A9C !important;
        color: #005A9C !important;
    }

    /* Dataframe header */
    .stDataFrame thead th {
        background-color: #e2e8f0;
        font-weight: 600;
    }

    /* Dividers */
    hr {
        border-color: #cbd5e1 !important;
    }

    /* ── End Theme ────────────────────────────────────────── */
    </style>
    """, unsafe_allow_html=True)

apply_theme()


# ═══════════════════════════════════════════════════════════════════
#  INITIALIZATION
# ═══════════════════════════════════════════════════════════════════

db = get_healthy_db()

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "parent_email" not in st.session_state:
    st.session_state["parent_email"] = ""
if "show_registration" not in st.session_state:
    st.session_state["show_registration"] = False


# ═══════════════════════════════════════════════════════════════════
#  VALIDATION HELPERS
# ═══════════════════════════════════════════════════════════════════

def validate_email(email: str) -> str | None:
    if not email or not email.strip():
        return "Email is required."
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email.strip()):
        return "Please enter a valid email address."
    return None


def validate_password(password: str) -> str | None:
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
    col_pad_l, col_form, col_pad_r = st.columns([1, 2, 1])
    with col_form:
        st.markdown("### 🛡️ Create Your Admin Account")
        st.caption("This account will manage all child devices in your family.")

        with st.form("registration_form"):
            email = st.text_input("Parent Email", placeholder="parent@example.com")
            password = st.text_input("Password", type="password", help="Min 8 chars, 1 uppercase, 1 digit")
            confirm = st.text_input("Confirm Password", type="password")
            submit = st.form_submit_button("Create Account", type="primary")

            if submit:
                email_err = validate_email(email)
                if email_err:
                    st.error(email_err)
                    return
                pwd_err = validate_password(password)
                if pwd_err:
                    st.error(pwd_err)
                    return
                if password != confirm:
                    st.error("Passwords do not match.")
                    return
                try:
                    db.register_parent(email.strip(), password)
                    st.success("✅ Account created! You can now log in.")
                    st.session_state["show_registration"] = False
                    st.rerun()
                except ValueError as ve:
                    st.error(str(ve))
                except Exception as e:
                    st.error(f"Registration failed: {e}")

        if st.button("← Back to Login"):
            st.session_state["show_registration"] = False
            st.rerun()


# ═══════════════════════════════════════════════════════════════════
#  LOGIN VIEW
# ═══════════════════════════════════════════════════════════════════

def login_view():
    col_pad_l, col_form, col_pad_r = st.columns([1, 2, 1])
    with col_form:
        st.markdown("### 🛡️ Warden Admin Login")
        with st.form("login_form"):
            email = st.text_input("Parent Email")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login", type="primary")

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

        if st.button("Don't have an account? Register here"):
            st.session_state["show_registration"] = True
            st.rerun()


# ═══════════════════════════════════════════════════════════════════
#  DASHBOARD VIEW
# ═══════════════════════════════════════════════════════════════════

def dashboard_view():
    # Sidebar
    st.sidebar.markdown("### 🛡️ Warden Control")
    st.sidebar.caption(f"Logged in as **{st.session_state['parent_email']}**")
    if st.sidebar.button("🚪 Logout"):
        st.session_state["logged_in"] = False
        st.session_state["parent_email"] = ""
        st.rerun()

    st.markdown("## Control Center")
    st.caption("Manage your family's screen time and application access from one place.")

    # ── Load children ──
    try:
        children = db.get_users_by_type("child")
    except Exception as e:
        st.error(f"Failed to load children: {e}")
        return

    # ── Section 1: Child & SID Management ──────────────────────────
    with st.container():
        st.markdown("### 👤 Child Management")

        if not children:
            st.info("No children connected yet. When a child PC connects, it will appear here automatically.")
        else:
            child_cols = st.columns(min(len(children), 4))
            for i, child in enumerate(children):
                with child_cols[i % len(child_cols)]:
                    st.markdown(f"**{child['name']}**")
                    st.caption(f"SID: `{child['sid'][:20]}...`" if child.get('sid') and len(child.get('sid', '')) > 20 else f"SID: `{child.get('sid', 'N/A')}`")

                    new_name = st.text_input("Rename", key=f"rename_{child['id']}", placeholder="Enter new name", label_visibility="collapsed")
                    if st.button("✏️ Save Name", key=f"save_name_{child['id']}"):
                        if new_name and new_name.strip():
                            try:
                                res = send_remote_command("assign_child_name", {
                                    "user_id": child["id"],
                                    "name": new_name.strip()
                                })
                                if res and res.get("status") == "success":
                                    st.success(f"Renamed to '{new_name.strip()}'")
                                    st.rerun()
                                else:
                                    st.error(f"Failed: {res}")
                            except Exception as e:
                                st.error(f"Error: {e}")
                        else:
                            st.warning("Please enter a name.")

    st.divider()

    # ── Section 2: Activity Monitor ─────────────────────────────────
    with st.container():
        st.markdown("### 📊 Activity Monitor")

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
                st.bar_chart(data=agg_df, x="app_name", y="duration", color="child_name")
                with st.expander("📋 View Raw Logs"):
                    st.dataframe(df_usage, use_container_width=True, hide_index=True)
            else:
                st.info("No activity logged today yet.")
        except Exception as e:
            st.error(f"Failed to load activity data: {e}")

    st.divider()

    if not children:
        return

    # ── Section 3: Rules & Remote Commands ──────────────────────────
    with st.container():
        st.markdown("### ⚙️ Rules & Remote Commands")

        tabs = st.tabs([f"👦 {child['name']}" for child in children])

        for idx, child in enumerate(children):
            with tabs[idx]:
                col_rules, col_commands = st.columns(2)

                with col_rules:
                    st.markdown("#### 📏 Active Rules")
                    try:
                        rules_query = "SELECT app_name, allowed_minutes FROM app_rules WHERE user_id = %s"
                        df_rules = db.get_dataframe_data(rules_query, params=(child['id'],))
                        if not df_rules.empty:
                            st.dataframe(df_rules, use_container_width=True, hide_index=True)
                        else:
                            st.info("No rules configured.")
                    except Exception as e:
                        st.error(f"Failed to load rules: {e}")

                    with st.form(f"rule_form_{child['id']}"):
                        st.markdown("**Add / Update Rule**")
                        app_input = st.text_input("App Name", key=f"app_{child['id']}", placeholder="e.g. mspaint.exe")
                        time_input = st.number_input("Allowed Minutes (0 = lock)", min_value=0, value=60, step=15, key=f"time_{child['id']}")
                        if st.form_submit_button("💾 Save Rule"):
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
                                        st.success(f"Rule saved for {app_input}")
                                        st.rerun()
                                    else:
                                        st.error(f"Failed: {res}")
                                except Exception as e:
                                    st.error(f"Error: {e}")

                with col_commands:
                    st.markdown("#### ⚡ Remote Commands")

                    target_app = st.text_input("Target App", key=f"target_{child['id']}", placeholder="e.g. chrome.exe", help="Name of the executable.")

                    cmd_col1, cmd_col2 = st.columns(2)
                    with cmd_col1:
                        if st.button("➕ Add 30 Min", key=f"add_{child['id']}", type="primary", use_container_width=True):
                            if not target_app:
                                st.error("Enter a target app first!")
                            else:
                                try:
                                    res = send_remote_command("add_time", {"user_id": child["id"], "app": target_app, "minutes": 30})
                                    if res and res.get("status") == "success":
                                        st.success(f"+30 min to {target_app}")
                                    else:
                                        st.error(f"Failed: {res}")
                                except Exception as e:
                                    st.error(f"Error: {e}")

                    with cmd_col2:
                        if st.button("🔓 Unlock 24h", key=f"unlock_{child['id']}", use_container_width=True):
                            if not target_app:
                                st.error("Enter a target app first!")
                            else:
                                try:
                                    res = send_remote_command("unlock_app", {"user_id": child["id"], "app": target_app})
                                    if res and res.get("status") == "success":
                                        st.success(f"{target_app} unlocked!")
                                    else:
                                        st.error(f"Failed: {res}")
                                except Exception as e:
                                    st.error(f"Error: {e}")

                    st.divider()
                    st.markdown("**🚨 Administrative Override**")
                    if st.button("🚨 Emergency Unlock", key=f"emer_{child['id']}", help="Instantly kills any active lock screen on this child's PC.", use_container_width=True):
                        try:
                            res = send_remote_command("emergency_unlock", {"user_id": child["id"]})
                            if res and res.get("status") == "success":
                                st.success("Emergency unlock signal sent!")
                            else:
                                st.error(f"Failed: {res}")
                        except Exception as e:
                            st.error(f"Error: {e}")

    st.divider()

    # ── Section 4: App Blocker ──────────────────────────────────────
    with st.container():
        st.markdown("### 🔒 App Blocker")
        st.caption("Search for known apps or add custom ones. Lock sets `allowed_minutes = 0`.")

        blocker_tabs = st.tabs([f"🔒 {child['name']}" for child in children])

        for idx, child in enumerate(children):
            with blocker_tabs[idx]:
                child_id = child["id"]

                # Fetch known apps
                known_apps = []
                try:
                    res = send_remote_command("get_known_apps", {"user_id": child_id})
                    if res and res.get("status") == "success":
                        known_apps = res.get("apps", [])
                except Exception:
                    pass
                if not known_apps:
                    try:
                        known_apps = db.get_known_apps(child_id)
                    except Exception:
                        known_apps = []

                # Fetch locked status from rules (single source of truth)
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

                # Search bar
                search_query = st.text_input(
                    "🔍 Search apps...", key=f"blocker_search_{child_id}",
                    placeholder="Type to filter (e.g. 'chrome', 'notepad')"
                )

                filtered_apps = [app for app in known_apps if search_query.strip().lower() in app.lower()] if search_query.strip() else known_apps

                if filtered_apps:
                    st.caption(f"**{len(filtered_apps)}** app(s) found")
                    for app_name in filtered_apps:
                        is_locked = app_name in locked_apps
                        col_name, col_status, col_action = st.columns([3, 1.5, 2])

                        with col_name:
                            st.write(f"📦 `{app_name}`")
                        with col_status:
                            if is_locked:
                                st.markdown('<div class="status-locked">🔴 Locked</div>', unsafe_allow_html=True)
                            else:
                                st.markdown('<div class="status-allowed">🟢 Allowed</div>', unsafe_allow_html=True)
                        with col_action:
                            if is_locked:
                                if st.button("🔓 Unlock", key=f"ub_{child_id}_{app_name}"):
                                    try:
                                        res = send_remote_command("unlock_app", {"user_id": child_id, "app": app_name})
                                        if res and res.get("status") == "success":
                                            st.success(f"Unlocked {app_name}")
                                            st.rerun()
                                        else:
                                            st.error(f"Failed: {res}")
                                    except Exception as e:
                                        st.error(f"Error: {e}")
                            else:
                                if st.button("🔒 Lock", key=f"lb_{child_id}_{app_name}"):
                                    try:
                                        res = send_remote_command("lock_app", {"user_id": child_id, "app": app_name})
                                        if res and res.get("status") == "success":
                                            st.success(f"Locked {app_name}")
                                            st.rerun()
                                        else:
                                            st.error(f"Failed: {res}")
                                    except Exception as e:
                                        st.error(f"Error: {e}")
                elif search_query.strip():
                    st.info(f"No apps matching '{search_query}' found.")
                else:
                    st.info("No known apps recorded yet. Use the form below to add one manually.")

                # Manual app entry
                st.divider()
                with st.form(f"custom_app_form_{child_id}"):
                    st.markdown("**Add Custom App**")
                    custom_app = st.text_input("Executable name", key=f"custom_app_{child_id}", placeholder="e.g. game.exe")
                    custom_action = st.selectbox("Action", ["Lock (0 minutes)", "Allow (60 minutes)", "Allow (120 minutes)"], key=f"custom_action_{child_id}")
                    if st.form_submit_button("Apply"):
                        if not custom_app.strip():
                            st.error("Please enter an app name.")
                        else:
                            minutes_map = {"Lock (0 minutes)": 0, "Allow (60 minutes)": 60, "Allow (120 minutes)": 120}
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
#  ROUTING
# ═══════════════════════════════════════════════════════════════════

if st.session_state["logged_in"]:
    dashboard_view()
elif st.session_state["show_registration"]:
    registration_view()
else:
    login_view()
