import re
import streamlit as st
import pandas as pd
from socket_manager import get_healthy_db, send_remote_command, start_event_listener, NEW_DEVICE_QUEUE

st.set_page_config(
    page_title="Warden - Parental Control", 
    layout="wide", 
    page_icon="🛡️",
    initial_sidebar_state="expanded"
)

# ═══════════════════════════════════════════════════════════════════
#  DEEP-BLUE / BLACK THEME (AMAZON-STYLE)
# ═══════════════════════════════════════════════════════════════════

def apply_theme():
    st.markdown("""
    <style>
    /* ── Modern Deep-Blue/Black Theme ───────────────────────── */

    /* Import Inter font from Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* Global Typography & Background */
    .stApp {
        background-color: #0A1929;
        font-family: 'Inter', sans-serif;
    }
    
    h1, h2, h3, h4, h5, h6, p, span, div, label {
        color: #F8FAFC !important;
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #0F172A;
        border-right: 1px solid #1E293B;
    }
    [data-testid="stSidebar"] * {
        color: #F8FAFC !important;
    }

    /* Primary buttons (Electric Blue) */
    .stButton>button, .stFormSubmitButton>button {
        background-color: #3B82F6;
        color: #F8FAFC !important;
        border-radius: 8px;
        border: none;
        font-weight: 600;
        transition: all 0.25s ease;
        font-family: 'Inter', sans-serif;
        padding: 0.5rem 1rem;
    }
    .stButton>button:hover, .stFormSubmitButton>button:hover {
        background-color: #2563EB;
        color: #FFFFFF !important;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
    }
    
    /* Specific styling for the Lock/Unlock actions to stand out visually */
    /* They use keys like ub_{child_id} and lb_{child_id} but st injects that */
    /* Target buttons with Lock/Unlock in their text */
    button:has(> div > span > p) {
        /* Generic, Streamlit buttons */
    }

    /* Input fields (Search Bar, etc) */
    .stTextInput input, .stNumberInput input {
        background-color: #1E293B !important;
        color: #F8FAFC !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
    }
    .stTextInput input:focus, .stNumberInput input:focus {
        border-color: #3B82F6 !important;
        box-shadow: 0 0 0 1px #3B82F6 !important;
    }
    /* Fix for selectbox */
    div[data-baseweb="select"] > div {
        background-color: #1E293B !important;
        color: #F8FAFC !important;
        border-color: #334155 !important;
    }

    /* Section card-like containers (Expanders & DataFrames) */
    [data-testid="stExpander"] {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 10px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    [data-testid="stExpander"] > div[role="button"] {
        background-color: transparent !important;
    }
    
    [data-testid="stDataFrame"] {
        background-color: #1E293B;
        border-radius: 10px;
        padding: 5px;
        border: 1px solid #334155;
    }

    /* Status chips */
    .status-allowed {
        background-color: rgba(16, 185, 129, 0.15);
        color: #34D399;
        padding: 5px 14px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85em;
        display: inline-block;
        letter-spacing: 0.02em;
        border: 1px solid rgba(52, 211, 153, 0.3);
    }
    .status-locked {
        background-color: rgba(239, 68, 68, 0.15);
        color: #F87171;
        padding: 5px 14px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85em;
        display: inline-block;
        letter-spacing: 0.02em;
        border: 1px solid rgba(248, 113, 113, 0.3);
    }

    /* Metric labels */
    [data-testid="stMetricLabel"] {
        color: #94A3B8 !important;
        font-weight: 500;
    }
    [data-testid="stMetricValue"] {
        color: #F8FAFC !important;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab"] {
        font-weight: 600;
        color: #94A3B8;
        background-color: transparent;
    }
    .stTabs [aria-selected="true"] {
        border-bottom-color: #3B82F6 !important;
        color: #F8FAFC !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 20px;
    }

    /* Dataframe header */
    .stDataFrame thead th {
        background-color: #0F172A;
        font-weight: 600;
        color: #F8FAFC !important;
    }

    /* Dividers with generous whitespace */
    hr {
        border-color: #334155 !important;
        margin: 2.5rem 0 !important;
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


import time

# ═══════════════════════════════════════════════════════════════════
#  CACHED DATA FETCHERS
# ═══════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3)
def get_known_apps_cached(child_id):
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
    return known_apps

@st.cache_data(ttl=2)
def get_locked_apps_cached(child_id):
    locked = set()
    try:
        rules_query = "SELECT app_name, allowed_minutes FROM app_rules WHERE user_id = %s"
        df_current_rules = db.get_dataframe_data(rules_query, params=(child_id,))
        if not df_current_rules.empty:
            for _, row in df_current_rules.iterrows():
                if row["allowed_minutes"] == 0:
                    locked.add(row["app_name"])
    except Exception:
        pass
    return locked

@st.fragment
def render_app_blocker(child):
    child_id = child["id"]

    def _toggle_lock(c_id, a_name, lock):
        cmd = "lock_app" if lock else "unlock_app"
        send_remote_command(cmd, {"user_id": c_id, "app": a_name})
        get_locked_apps_cached.clear()

    # Fetch data using caching
    known_apps = get_known_apps_cached(child_id)
    locked_apps = get_locked_apps_cached(child_id)

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
                    st.button("🔓 Unlock", key=f"ub_{child_id}_{app_name}", on_click=_toggle_lock, args=(child_id, app_name, False))
                else:
                    st.button("🔒 Lock", key=f"lb_{child_id}_{app_name}", on_click=_toggle_lock, args=(child_id, app_name, True))
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
                        get_locked_apps_cached.clear()
                        get_known_apps_cached.clear()
                        st.rerun()
                    else:
                        st.error(f"Failed: {res}")
                except Exception as e:
                    st.error(f"Error: {e}")

# ═══════════════════════════════════════════════════════════════════
#  DASHBOARD VIEW
# ═══════════════════════════════════════════════════════════════════

@st.fragment(run_every=2)
def poll_new_devices():
    """Polls the background thread queue for real-time new device alerts."""
    if NEW_DEVICE_QUEUE:
        for sid in list(NEW_DEVICE_QUEUE):
            st.toast(f"New Device Connected! (SID: {sid})", icon="🚨")
            try:
                NEW_DEVICE_QUEUE.remove(sid)
            except ValueError:
                pass
        st.rerun()

def dashboard_view():
    # Start background listener if not already running
    start_event_listener()
    
    # Poll for real-time alerts
    poll_new_devices()
    # Sidebar
    st.sidebar.markdown("### 🛡️ Warden Control")
    st.sidebar.caption(f"Logged in as **{st.session_state['parent_email']}**")
    if st.sidebar.button("🚪 Logout"):
        st.session_state["logged_in"] = False
        st.session_state["parent_email"] = ""
        st.rerun()

    if st.sidebar.button("🔄 Refresh Data", type="primary", use_container_width=True):
        # Force DB to see latest committed data
        db.force_fresh_read()
        # Clear all cached data
        get_known_apps_cached.clear()
        get_locked_apps_cached.clear()
        st.cache_data.clear()
        st.rerun()

    st.sidebar.divider()
    st.sidebar.caption("💡 Data auto-refreshes every 3 seconds.")

    st.markdown("## Control Center")
    st.caption("Manage your family's screen time and application access from one place.")

    # ── Load children ──
    try:
        children = db.get_users_by_type("child")
        # Filter active children vs pending
        active_children = [c for c in children if c.get('status', 'ACTIVE') == 'ACTIVE']
        # Also need to fetch pending explicitly because get_users_by_type doesn't return status directly in old schema,
        # but our new get_pending_devices handles it!
        pending_devices = db.get_pending_devices()
    except Exception as e:
        st.error(f"Failed to load children: {e}")
        return

    # ── Section 0: Unassigned Devices ──────────────────────────────
    if pending_devices:
        with st.container():
            st.markdown("### 🆕 Unassigned Devices")
            st.warning("These devices have connected to the network and are awaiting setup.")
            
            for pending in pending_devices:
                with st.expander(f"Setup Device: {pending['sid']}", expanded=True):
                    with st.form(f"setup_form_{pending['id']}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            new_name = st.text_input("Device Owner Name", placeholder="e.g. Child's Laptop")
                        with col2:
                            blacklisted_app = st.text_input("Initial Blacklisted App (Optional)", placeholder="e.g. chrome.exe")
                            
                        if st.form_submit_button("Complete Setup", type="primary"):
                            if new_name.strip():
                                try:
                                    res = send_remote_command("assign_child_name", {
                                        "user_id": pending["id"],
                                        "name": new_name.strip()
                                    })
                                    if blacklisted_app.strip():
                                        send_remote_command("lock_app", {
                                            "user_id": pending["id"],
                                            "app": blacklisted_app.strip()
                                        })
                                    st.success(f"Setup complete for {new_name.strip()}!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Setup failed: {e}")
                            else:
                                st.error("Please enter a name for the device.")
            
        st.divider()

    # ── Section 1: Child & SID Management ──────────────────────────
    with st.container():
        st.markdown("### 👤 Child Management")

        if not active_children:
            st.info("No children connected yet. When a child PC connects, it will appear here automatically.")
        else:
            child_cols = st.columns(min(len(active_children), 4))
            for i, child in enumerate(active_children):
                with child_cols[i % len(child_cols)]:
                    st.markdown(f"**{child['name']}**")
                    st.caption(f"SID: `{child['sid'][:20]}...`" if child.get('sid') and len(child.get('sid', '')) > 20 else f"SID: `{child.get('sid', 'N/A')}`")
                    
                    if st.button("Delete Device", key=f"delete_init_{child['id']}", type="secondary"):
                        st.session_state[f"confirm_delete_{child['id']}"] = True
                        
                    if st.session_state.get(f"confirm_delete_{child['id']}", False):
                        st.warning(f"Are you sure you want to completely remove {child['name']}? This will delete all logs and rules permanently.")
                        col_confirm, col_cancel = st.columns(2)
                        with col_confirm:
                            if st.button("Confirm", key=f"delete_confirm_{child['id']}", type="primary"):
                                try:
                                    send_remote_command("remove_child", {"user_id": child["id"]})
                                    st.success(f"{child['name']} removed successfully.")
                                    del st.session_state[f"confirm_delete_{child['id']}"]
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Failed to remove child: {e}")
                        with col_cancel:
                            if st.button("Cancel", key=f"delete_cancel_{child['id']}"):
                                del st.session_state[f"confirm_delete_{child['id']}"]
                                st.rerun()
                                
                    st.divider()

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
    @st.fragment(run_every=3)
    def _activity_monitor_fragment():
        db.force_fresh_read()
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

    _activity_monitor_fragment()

    st.divider()

    if not active_children:
        return

    # ── Section 3: Rules & Remote Commands ──────────────────────────
    with st.container():
        st.markdown("### ⚙️ Rules & Remote Commands")

        tabs = st.tabs([f"👦 {child['name']}" for child in active_children])

        for idx, child in enumerate(active_children):
            with tabs[idx]:
                col_rules, col_commands = st.columns(2)

                with col_rules:
                    @st.fragment(run_every=3)
                    def _rules_fragment(child_id=child['id']):
                        db.force_fresh_read()
                        st.markdown("#### 📏 Active Rules")
                        try:
                            rules_query = "SELECT app_name, allowed_minutes FROM app_rules WHERE user_id = %s"
                            df_rules = db.get_dataframe_data(rules_query, params=(child_id,))
                            if not df_rules.empty:
                                st.dataframe(df_rules, use_container_width=True, hide_index=True)
                            else:
                                st.info("No rules configured.")
                        except Exception as e:
                            st.error(f"Failed to load rules: {e}")
                    _rules_fragment()

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

        blocker_tabs = st.tabs([f"🔒 {child['name']}" for child in active_children])

        for idx, child in enumerate(active_children):
            with blocker_tabs[idx]:
                render_app_blocker(child)



# ═══════════════════════════════════════════════════════════════════
#  ROUTING
# ═══════════════════════════════════════════════════════════════════

if st.session_state["logged_in"]:
    dashboard_view()
elif st.session_state["show_registration"]:
    registration_view()
else:
    login_view()
