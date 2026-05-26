# קוד פרויקט Warden - קטעי קוד מוסברים עבור בעיות אלגוריתמיות (חלק ב')

קובץ זה מרכז את קטעי הקוד הראשיים של מערכת **Warden** כחלק מפרק ב' של ספר הפרויקט. עבור כל אחת משלוש הבעיות האלגוריתמיות שנדונו, מפורט קטע הקוד הרלוונטי והסבר תפקידו במערכת. 

כל קטעי הקוד מלווים ב**הערות קצרות באנגלית בשורה אחת בלבד** (`single-line comments`) בהתאם לכללי התכנות הנכונים.

---

## 1. בעיה ראשונה: הזרקת מסך הנעילה (עקיפת Session 0)

### תיאור הבעיה ופתרונה
שירות המערכת (`WardenService`) רץ ברקע תחת סביבה מבודדת ומחוסרת ממשק גרפי (Session 0). כדי להציג את מסך החסימה לילד, השירות מאתר את מזהה הסשן הפיזי האקטיבי (`Session ID`), שולף את אסימון האבטחה (`Token`) של המשתמש הפעיל, משכפל אסימון מערכת בעל הרשאות גבוהות המותאם לסשן זה, ומשגר את תהליך מסך הנעילה (`lock_screen.exe`) ישירות אל שולחן העבודה האינטראקטיבי שלו (`winsta0\default`).

### קטע הקוד
* **קובץ מקור:** [service.py](file:///c:/Users/porat/Downloads/כיתה%20יב/פרויקט%20סייבר/ParentalControl/src/warden_client/service.py) (שורות 419 עד 659)

```python
    def launch_lock_screen(self):
        self.log_session_debug_info()
        
        # Prevent double execution if lock screen is already running
        if hasattr(self, 'lock_screen_process') and self.lock_screen_process:
            try:
                if getattr(self.lock_screen_process, 'poll', lambda: 0)() is None:
                    self.logger.info("Lock screen is already running in the active session.")
                    return
            except Exception:
                pass
                
        try:
            script_path = Path(__file__).resolve().parent / "lock_manager" / "lock_screen.py"
            cmd_args = None

            launched_as_user = False
            if HAS_WIN32:
                try:
                    import win32process
                    import win32security
                    import win32con
                    import win32ts
                    import win32profile
                    import win32api
                    import ctypes

                    # Step 1: Identify the active console session ID
                    session_id = ctypes.windll.kernel32.WTSGetActiveConsoleSessionId()
                    if session_id == 0xFFFFFFFF:
                        raise RuntimeError("No active physical console session identified.")
                    self.logger.info(f"Active console session ID detected: {session_id}")

                    # Step 2: Query active user token with retries for fast switching
                    user_token = None
                    for attempt in range(15):
                        try:
                            curr_sess = ctypes.windll.kernel32.WTSGetActiveConsoleSessionId()
                            if curr_sess != 0xFFFFFFFF and curr_sess != session_id:
                                self.logger.info(f"Active session shifted to {curr_sess}. Updating target.")
                                session_id = curr_sess

                            user_token = win32ts.WTSQueryUserToken(session_id)
                            if user_token:
                                break
                        except Exception as e:
                            err_code = getattr(e, 'winerror', 0)
                            self.logger.info(f"Token not ready yet (attempt {attempt+1}/15, Windows Error: {err_code}). Retrying in 1s...")
                            time.sleep(1)
                    
                    if not user_token:
                        raise RuntimeError(f"Failed to query User Token for session {session_id} after retries.")

                    # Step 3: Duplicate SYSTEM token and set session ID
                    hProcess = win32api.GetCurrentProcess()
                    hToken = win32security.OpenProcessToken(hProcess, win32security.TOKEN_ALL_ACCESS)
                    
                    sys_token = win32security.DuplicateTokenEx(
                        hToken,
                        win32security.SecurityImpersonation,
                        win32security.TOKEN_ALL_ACCESS,
                        win32security.TokenPrimary,
                        None
                    )
                    win32security.SetTokenInformation(sys_token, win32security.TokenSessionId, session_id)

                    # Step 4: Determine path (frozen executable vs source python script)
                    if getattr(sys, "frozen", False):
                        exe_path = Path(sys.executable).with_name("lock_screen.exe")
                        if not exe_path.exists():
                            raise FileNotFoundError("lock_screen.exe missing in base directory.")
                        cmd_args = [str(exe_path)]
                    else:
                        python_exe = str(Path(sys.base_prefix) / "python.exe")
                        if not Path(python_exe).exists():
                            python_exe = str(Path(sys.base_prefix) / "Scripts" / "python.exe")
                        self.logger.info(f"Using standard python executable: {python_exe}")
                        cmd_args = [python_exe, str(script_path)]

                    # Append target locked app name as parameter
                    if self.locked_app_name:
                        cmd_args.extend(["--app", self.locked_app_name])

                    # Step 5: Build interactive environment block for target user
                    environment = win32profile.CreateEnvironmentBlock(user_token, False)

                    # Inject PYTHONPATH environment variable if running from source
                    if not getattr(sys, "frozen", False):
                        pythonpath_val = str(Path(__file__).resolve().parent.parent)
                        if isinstance(environment, dict):
                            environment["PYTHONPATH"] = pythonpath_val
                        else:
                            extra_var = f"PYTHONPATH={pythonpath_val}\0"
                            if environment.endswith('\0\0'):
                                environment = environment[:-1] + extra_var + '\0'
                            else:
                                environment = environment + extra_var + '\0'

                    # Step 6: Configure process startup targeting interactive desktop
                    startup = win32process.STARTUPINFO()
                    startup.lpDesktop = "winsta0\\default"
                    startup.dwFlags = win32process.STARTF_USESHOWWINDOW
                    startup.wShowWindow = win32con.SW_SHOW

                    cmd_str = subprocess.list2cmdline(cmd_args)
                    working_dir = str(Path(__file__).resolve().parent / "lock_manager")
                    creation_flags = (
                        win32process.CREATE_NEW_PROCESS_GROUP |
                        win32process.CREATE_UNICODE_ENVIRONMENT |
                        win32con.NORMAL_PRIORITY_CLASS
                    )

                    self.logger.info(f"Executing CreateProcessAsUser with command: {cmd_str}")

                    # Step 7: Launch the lock screen process in user session
                    hProcess, hThread, dwProcessId, dwThreadId = win32process.CreateProcessAsUser(
                        sys_token,
                        None,
                        cmd_str,
                        None,
                        None,
                        False,
                        creation_flags,
                        environment,
                        working_dir,
                        startup
                    )

                    # Close unused thread and token handles
                    win32api.CloseHandle(hThread)
                    win32api.CloseHandle(user_token)
                    win32api.CloseHandle(sys_token)
                    self.logger.info(f"Successfully launched lock screen in User Session {session_id} (PID: {dwProcessId})")

                    # Wrap Win32 process handles for polling and killing
                    class WinProcessWrapper:
                        def __init__(self, hp, pid):
                            self.hProcess = hp
                            self.pid = pid
                        def poll(self):
                            import win32event, win32process as wp
                            status = win32event.WaitForSingleObject(self.hProcess, 0)
                            if status == win32event.WAIT_TIMEOUT:
                                return None
                            return wp.GetExitCodeProcess(self.hProcess)
                        def kill(self):
                            try:
                                win32api.TerminateProcess(self.hProcess, 1)
                            except Exception:
                                pass

                    self.lock_screen_process = WinProcessWrapper(hProcess, dwProcessId)
                    launched_as_user = True

                    # Step 8: Perform post-launch process health check
                    time.sleep(2)
                    exit_code = self.lock_screen_process.poll()
                    if exit_code is not None:
                        self.logger.error(f"Lock screen process crashed with exit code: {exit_code}")
                        self.lock_screen_process = None
                        launched_as_user = False

                except Exception as e:
                    self.logger.warning(f"CreateProcessAsUser bypass failed: {e}. Falling back to Popen.")

            # Fallback to standard Popen when running outside Windows Service context
            if not launched_as_user:
                self.logger.warning("Launching lock screen via fallback subprocess Popen.")
                if getattr(sys, "frozen", False):
                    fallback_cmd = cmd_args if cmd_args else [sys.executable]
                else:
                    python_exe = str(Path(sys.base_prefix) / "python.exe")
                    fallback_cmd = [python_exe, str(script_path)]
                    if self.locked_app_name:
                        fallback_cmd.extend(["--app", self.locked_app_name])
                
                self.lock_screen_process = subprocess.Popen(
                    fallback_cmd,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                )
                self.logger.info(f"Lock screen fallback launched (PID: {self.lock_screen_process.pid})")
        except Exception as exc:
            self.logger.error("Failed to launch lock screen completely: %s", exc)
```

---

## 2. בעיה שנייה: ניטור תהליכים יעיל (Smart Polling & Cache)

### תיאור הבעיה ופתרונה
ניטור תהליכים מחזורי יכול לגרום לעומס רב על המעבד (CPU). כדי לפתור זאת, פיתחנו את אלגוריתם ה-`Delta Cache` במחלקת `TimeTracker`. המערכת שולפת את ה-SID של כל תהליך במערכת באופן בטוח, ומסננת מיידית תהליכים שאינם שייכים לילד. לאחר מכן, היא משווה את התהליכים הרצים מול זיכרון מטמון מקומי (`active_processes`) ומחשבת אך ורק את ה"הפרש" (Delta) - תהליכים חדשים שנפתחו (`APP_STARTED`) או נסגרו (`APP_STOPPED`) - בסיבוכיות חיפוש של $O(1)$.

### קטע הקוד
* **קובץ מקור:** [time_tracker.py](file:///c:/Users/porat/Downloads/כיתה%20יב/פרויקט%20סייבר/ParentalControl/src/warden_client/time_tracker.py) (שורות 9 עד 91)

```python
import psutil
import win32security
import win32con
import logging
from datetime import datetime
import time
from datetime import timezone

class TimeTracker:

    def __init__(self):
        self.logger = logging.getLogger("process_tracker")
        # Global cache dictionary mapping active processes: pid -> app_name
        self.active_processes = {}

    def get_sid_of_process(self, pid):
        try:
            if not psutil.pid_exists(pid):
                return None
                
            process = psutil.Process(pid)
            import win32process
            import win32api
            import win32security
            import pywintypes

            try:
                # 1. Try to open process token for query information
                hProcess = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION, False, pid)
                hToken = win32security.OpenProcessToken(hProcess, win32con.TOKEN_QUERY)
                # 2. Extract security identifier object from token
                user_sid, _ = win32security.GetTokenInformation(hToken, win32security.TokenUser)
                win32api.CloseHandle(hToken)
                win32api.CloseHandle(hProcess)
                # 3. Convert binary SID object to string representation
                return win32security.ConvertSidToStringSid(user_sid)
            except Exception:
                # Fallback to username lookup if direct token reading fails
                username = process.username()
                if not username:
                    return None
                # Strip domain name prefix if present
                if '\\' in username:
                    username = username.split('\\')[-1]
                # Convert active username to SID via OS query
                sid_obj, _, _ = win32security.LookupAccountName(None, username)
                return win32security.ConvertSidToStringSid(sid_obj)
        except Exception as exc:
            self.logger.debug("Failed to resolve SID for pid=%s: %s", pid, exc)
            return None

    def scan_processes(self, target_sid):
        current_processes = {}
        events = []
        
        # Step 1: Scan all active processes in system
        for proc in psutil.process_iter(['pid','name']):
            try:
                pid = proc.info['pid']
                name = proc.info['name']

                # Filter process to only include target user SID
                sid = self.get_sid_of_process(pid)
                if sid != target_sid:
                    continue
                
                current_processes[pid] = name
                
                # Step 2: Detect newly started processes
                if pid not in self.active_processes:
                    events.append({
                        "event_name": "APP_STARTED",
                        "app": name,
                        "pid": pid,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # Handle processes closing during scan or query denial
                continue

        # Step 3: Detect terminated processes
        for pid in list(self.active_processes):
            if pid not in current_processes:
                events.append({
                    "event_name": "APP_STOPPED",
                    "app": self.active_processes[pid],
                    "pid": pid,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

        # Step 4: Update active processes cache for next loop
        self.active_processes = current_processes

        return events
```

---

## 3. בעיה שלישית: סנכרון רציף של חוקי השרת בזמן אמת (TCP Push & Reconciliation)

### תיאור הבעיה ופתרונה
כדי לאפשר להורה לשנות חוקים או להעניק תוספת זמן מרחוק בזמן אמת (Real-Time), פותח ערוץ תקשורת דו-כיווני קבוע מבוסס TCP Sockets מוצפנים (AES-256 GCM). 

השרת דוחף פקודות ישירות ללקוח, והלקוח מבצע אלגוריתם **Local Reconciliation** (התאמה מקומית): הוא מעדכן את מצב הזמנים הפעיל ומבצע הצלבה מול הזמן שנמדד מקומית כדי לקבוע מיידית האם לנעול את המסך או לשחררו ללא צורך בהמתנה.

### קטעי הקוד

#### א. שליחת פקודת Push בזמן אמת מהשרת
* **קובץ מקור:** [main.py (Server)](file:///c:/Users/porat/Downloads/כיתה%20יב/פרויקט%20סייבר/ParentalControl/src/warden_server/main.py) (שורות 258 עד 281)

```python
    def _push_command(self, sid, action, app=None):
        client_info = None
        # Safely fetch client socket and AES key using lock
        with self.clients_lock:
            client_info = self.clients_by_sid.get(sid)

        if not client_info:
            self.logger.warning(f"No connected client found for SID {sid} to send {action} command")
            return False

        self.logger.info(f"Pushing {action} command to SID {sid}" + (f" for app {app}" if app else ""))

        try:
            # 1. Build communication payload
            payload = {"action": action, "sid": sid}
            if app:
                payload["app"] = app
                
            # 2. Serialize payload dictionary to JSON byte format
            msg = Protocol.serialize_message(action, payload)
            
            # 3. Encrypt payload utilizing AES session key
            encrypted = CryptoManager.encrypt_aes(client_info["aes_key"], msg)
            
            # 4. Thread-safe write to network socket with dedicated lock
            with client_info["write_lock"]:
                Protocol.send_packet(client_info["sock"], encrypted)
                
            self.logger.info(f"Sent {action} command to {sid} successfully.")
            return True
        except Exception as e:
            self.logger.exception(f"Failed to send {action} command to {sid}: {e}")
            return False
```

#### ב. קבלת הפקודה וביצוע התאמה מקומית בלקוח (Local Reconciliation)
* **קובץ מקור:** [service.py (Client)](file:///c:/Users/porat/Downloads/כיתה%20יב/פרויקט%20סייבר/ParentalControl/src/warden_client/service.py) (שורות 377 עד 404)

```python
        elif normalized_action == "time_update_signal":
            # Handle real-time time limit updates from server
            if isinstance(data, dict):
                # Verify that command targets the current active user SID
                target_sid = data.get("sid", "")
                if target_sid and target_sid != self.sid:
                    self.logger.info("Ignoring TIME_UPDATE_SIGNAL meant for SID %s (Current: %s)", target_sid, self.sid)
                    return
            
            app_name = data.get("app", "").lower()
            new_allowed = data.get("new_allowed_minutes", 0.0)
            
            # Update local state allowed limit
            if app_name not in self.app_states:
                self.app_states[app_name] = {"total_used_time": 0.0, "allowed_minutes": new_allowed}
            
            self.app_states[app_name]["allowed_minutes"] = new_allowed
            used = self.app_states[app_name]["total_used_time"]
            
            self.logger.info("Reconciliation check for %s: allowed=%.2f, used=%.2f", app_name, new_allowed, used)
            
            # --- Local Reconciliation Logic ---
            if new_allowed > used:
                # Allowed minutes exceed usage - unlock app and close lock screen
                self.logger.info("Local Reconciliation: Unlocking app %s", app_name)
                if self.locked_app_name and self.locked_app_name.lower() == app_name:
                    self.locked_app_name = None
                self.kill_lock_screen()
            else:
                # Usage exceeds or equals new allowed minutes - enforce lock screen
                self.logger.info("Local Reconciliation: Enforcing lockout for app %s", app_name)
                self.locked_app_name = app_name
                self.launch_lock_screen()
            
            # Send message acknowledgment back to server
            self.send_message("ack_time_update", {"app": app_name})
```
