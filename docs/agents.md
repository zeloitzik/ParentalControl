# agents.md

## Project Overview

Warden is an event-driven parental control system.

The system consists of:

* A Windows service running on the child device
* A server that receives events and decides whether an application is allowed
* A database that stores users, rules, sessions, and usage history
* A parent dashboard that displays usage in real time

The architecture is intentionally split into client and server responsibilities.

---

# System Architecture

```text
Windows Service
    ↓
TimeTracker / Process Monitor
    ↓
HTTP JSON Events
    ↓
FastAPI Server
    ↓
ServerEngine
    ↓
MySQL Database
    ↓
Decision: ALLOW / BLOCK
    ↓
Parent Dashboard
```

---

# Agents

## 1. Windows Service Agent

File example:

* service.py

Purpose:

* Runs continuously in the background on the child computer
* Detects the currently logged-in SID
* Detects process start and stop events
* Communicates with the server
* Kills blocked processes

Responsibilities:

* Track the active user SID
* Poll running processes every few seconds
* Send events to the server
* Ask the server whether an app may run

Important fields:

```python
self.server_url = "http://127.0.0.1:8000"
self.user_SID
self.active_processes = {}
```

Important methods:

```python
def check_logged_user()
def monitor_processes()
def send_event(event_name, metadata)
def check_with_server(app_name)
```

Typical flow:

```text
Process starts
    ↓
check_with_server()
    ↓
If blocked → kill process
If allowed → send APP_STARTED event
```

---

## 2. TimeTracker Agent

File example:

* time_tracker.py

Purpose:

* Tracks processes belonging to a specific SID
* Converts process ownership to a SID
* Detects process start and stop transitions

Responsibilities:

* Match PID → username → SID
* Maintain a dictionary of active processes
* Emit logical events:

  * APP_STARTED
  * APP_STOPPED

Internal state:

```python
self.active_processes = {
    pid: process_name
}
```

Returned event format:

```python
{
    "event_name": "APP_STARTED",
    "app": "Fortnite.exe",
    "pid": 1234,
    "timestamp": "2026-03-29T18:00:00"
}
```

Important note:

* TimeTracker should not calculate total usage time directly.
* It should only detect process state changes.
* The server is responsible for duration calculations.

---

## 3. Event Agent

Purpose:

* Standardizes communication between the client and server

All events must be JSON and contain:

```json
{
  "sid": "S-1-5-21-...",
  "event_name": "APP_STARTED",
  "metadata": {
    "app": "Fortnite.exe"
  },
  "timestamp": "2026-03-29T18:00:00"
}
```

Supported event names:

* APP_STARTED
* APP_STOPPED
* USER_LOGIN
* USER_LOGOUT

Rules:

* Timestamps must be ISO-8601
* SID must always be included
* metadata should include app name where relevant

---

## 4. FastAPI Server Agent

File example:

* server.py

Purpose:

* Listens continuously for HTTP requests
* Routes requests to the correct logic

The server is started with:

```bash
uvicorn server:app --reload
```

Main endpoints:

```text
POST /event
POST /check_app
GET  /parent_dashboard
```

Endpoint behavior:

### POST /event

Receives an event and forwards it to ServerEngine.

```python
engine.process_event(event)
```

### POST /check_app

Receives:

```json
{
  "sid": "...",
  "app": "Fortnite.exe"
}
```

Returns:

```json
{
  "allowed": true
}
```

### GET /parent_dashboard

Returns live data for all child users and all tracked applications.

---

## 5. ServerEngine Agent

File example:

* engine.py

Purpose:

* Core decision-making engine
* Calculates time usage
* Decides whether an app may continue running

Main responsibilities:

* Process incoming events
* Start and stop app sessions
* Save completed usage sessions
* Handle missing APP_STOPPED events
* Enforce app limits

Core formula:

```text
Duration = stop_time - start_time
```

Main methods:

```python
def process_event(event)
def can_user_run_app(sid, app_name)
def handle_app_started(...)
def handle_app_stopped(...)
def cleanup_stale_sessions()
```

Decision flow:

```text
1. Find user by SID
2. Find rule for the app
3. Calculate total usage today
4. Add currently active session time
5. Compare against allowed_minutes
6. Return ALLOW or BLOCK
```

Pseudo-code:

```python
if total_time >= allowed_minutes:
    return False
return True
```

Important behavior:

* If an app session is still open, its running time must still count.
* Missing APP_STOPPED events must not allow bypassing limits.

---

# Database Design

Database:

* MySQL

Required tables:

## users

```text
id
name
sid
type
```

type values:

* parent
* child

---

## app_rules

```text
id
user_id
app_name
allowed_minutes
```

Example:

```text
ChildA + Fortnite.exe + 60 minutes
```

---

## app_sessions

Tracks currently running applications.

```text
id
user_id
app_name
start_time
end_time
status
```

status values:

* RUNNING
* CLOSED

Purpose:

* Used to track active applications
* Used when APP_STOPPED is missing

---

## usage_logs

Stores completed sessions.

```text
id
user_id
app_name
start_time
end_time
duration
```

Duration is stored in minutes.

---

# DatabaseManager Responsibilities

File example:

* database.py

Required methods:

```python
def get_user_id_by_sid(sid)
def get_app_rule(user_id, app_name)
def get_used_time_today(user_id, app_name)
def get_active_session_time(user_id, app_name)
def start_app_session(user_id, app_name, start_time)
def stop_app_session(user_id, app_name, stop_time)
def save_usage_log(...)
def clear_table(table_name)
def clear_database()
```

Important:

* app_sessions should be indexed by user_id and app_name
* users.sid should be indexed
* app_rules should be indexed by user_id and app_name

---

# Parent Dashboard Agent

Purpose:

* Displays real-time app usage to the parent

Returned API format:

```json
[
  {
    "name": "ChildA",
    "apps": [
      {
        "app": "Fortnite.exe",
        "used": 58,
        "allowed": 60
      }
    ]
  }
]
```

The dashboard should refresh every 2–3 seconds.

Example display:

```text
ChildA
Fortnite.exe: 58 / 60 minutes
Chrome.exe: 32 / 120 minutes
```

Future improvements:

* Progress bars
* Graphs
* Parent login system
* Force block button

---

# Failure Handling

The system should fail safely.

Recommended rules:

* If the server is unavailable, the service may temporarily allow apps
* Prefer adding a local rule cache later
* All exceptions should be logged
* Stale RUNNING sessions should be cleaned periodically

Recommended cleanup:

```python
cleanup_stale_sessions(timeout_minutes=10)
```

Example:

* If an app session has been RUNNING for 10+ minutes without updates and the process no longer exists, close it automatically.

---

# Recommended Future Features

1. Local rule cache on the client
2. Authentication token between service and server
3. Multiple devices per child
4. Parent login and authorization
5. Better UI with charts
6. Replace polling with WMI or ETW process events
7. Remote blocking from dashboard
8. Notification when time is nearly exhausted

---

# Project Philosophy

Warden should follow these principles:

* Thin client, smart server
* Event-driven architecture
* Real-time enforcement
* Server calculates time, not the client
* Parent dashboard is read-only unless explicit control features are added
* Every process state change should become an event
