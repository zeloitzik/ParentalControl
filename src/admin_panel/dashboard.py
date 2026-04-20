import streamlit as st
import pandas as pd
from socket_manager import get_db, send_remote_command

st.set_page_config(page_title="Parental Control Admin", layout="wide", page_icon="🛡️")

# --- INITIALIZATION ---
db = get_db()
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "parent_email" not in st.session_state:
    st.session_state["parent_email"] = ""

# --- LOGIN SECTION ---
def login_view():
    st.title("🛡️ Admin Dashboard Login")
    
    with st.form("login_form"):
        email = st.text_input("Parent Email")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            if db.verify_admin(email, password):
                st.session_state["logged_in"] = True
                st.session_state["parent_email"] = email
                st.rerun()
            else:
                st.error("Invalid email or password.")

# --- DASHBOARD SECTION ---
def dashboard_view():
    st.sidebar.title(f"Welcome, {st.session_state['parent_email']}")
    if st.sidebar.button("Logout"):
        st.session_state["logged_in"] = False
        st.session_state["parent_email"] = ""
        st.rerun()
        
    st.title("Control Center")
    
    # Activity Visualization Tab
    st.header("📊 Activity Monitor")
    
    # Query today's usage logs from DB
    usage_query = """
    SELECT u.name as child_name, ul.app_name, ul.duration, ul.start_time
    FROM usage_logs ul
    JOIN users u ON ul.user_id = u.id
    WHERE DATE(ul.start_time) = CURDATE()
    """
    df_usage = db.get_dataframe_data(usage_query)
    
    if not df_usage.empty:
        # Aggregate by child and app
        agg_df = df_usage.groupby(['child_name', 'app_name'])['duration'].sum().reset_index()
        
        # Display as Bar Chart
        st.subheader("Today's App Usage (Minutes)")
        st.bar_chart(data=agg_df, x="app_name", y="duration", color="child_name")
        
        # Display raw data table
        with st.expander("View Raw Logs"):
            st.dataframe(df_usage, use_container_width=True)
    else:
        st.info("No activity logged today yet.")


    st.divider()

    # Rule Management & Remote Commands Grid
    st.header("⚙️ Rules & Overrides")
    
    children = db.get_users_by_type("child")
    if not children:
        st.warning("No children found in the database. Please register them first.")
        return
        
    # Create tabs for each child
    tabs = st.tabs([child["name"] for child in children])
    
    for idx, child in enumerate(children):
        with tabs[idx]:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Manage Rules")
                # Fetch existing rules
                rules_query = f"SELECT app_name, allowed_minutes FROM app_rules WHERE user_id = {child['id']}"
                df_rules = db.get_dataframe_data(rules_query)
                st.dataframe(df_rules, use_container_width=True, hide_index=True)
                
                with st.form(f"rule_form_{child['id']}"):
                    st.write("Add / Update Rule")
                    app_input = st.text_input("App Name (e.g. mspaint.exe)", key=f"app_{child['id']}")
                    time_input = st.number_input("Allowed Minutes (0 to delete)", min_value=0, value=60, step=15, key=f"time_{child['id']}")
                    if st.form_submit_button("Save Rule"):
                        # Send command to server instead of DB direct so server caches clear immediately
                        res = send_remote_command("update_rule", {
                            "user_id": child["id"],
                            "app": app_input,
                            "allowed": time_input
                        })
                        if res and res.get("status") == "success":
                            st.success(f"Rule updated for {app_input}")
                            st.rerun()
                        else:
                            st.error(f"Failed to update rule: {res}")
                            
            with col2:
                st.subheader("⚡ Remote Commands")
                st.info("These commands are sent instantly over the socket protocol.")
                
                target_app = st.text_input("Target App for Override", key=f"target_{child['id']}", help="Name of the executable.")
                
                # Add Time Button
                if st.button("➕ Add 30 Minutes", key=f"add_{child['id']}", type="primary"):
                    if not target_app:
                        st.error("Please enter a Target App!")
                    else:
                        res = send_remote_command("add_time", {
                            "user_id": child["id"],
                            "app": target_app,
                            "minutes": 30
                        })
                        if res and res.get("status") == "success":
                            st.success(f"Added 30 minutes to {target_app}!")
                        else:
                            st.error(f"Command failed: {res}")
                            
                # Force Unlock Button
                if st.button("🔓 Force Unlock (24h)", key=f"unlock_{child['id']}"):
                    if not target_app:
                        st.error("Please enter a Target App!")
                    else:
                        res = send_remote_command("unlock_app", {
                            "user_id": child["id"],
                            "app": target_app
                        })
                        if res and res.get("status") == "success":
                            st.success(f"{target_app} has been unlocked!")
                        else:
                            st.error(f"Command failed: {res}")


# --- MAIN LOGIC ---
if st.session_state["logged_in"]:
    dashboard_view()
else:
    login_view()
