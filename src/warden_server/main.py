import sys
import os
from pathlib import Path

# Add src to sys.path if running as script to allow absolute imports
current_dir = Path(__file__).resolve().parent
if (current_dir.parent / "warden_core").exists():
    sys.path.append(str(current_dir.parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi import Request
from pydantic import BaseModel 
from warden_core.database import DatabaseManager
from warden_core.engine import ServerEngine
from warden_core.setup_logger import my_logger
import logging
app = FastAPI()

# init
db = DatabaseManager()
engine = ServerEngine(db)
logger = my_logger("server", "server.log").setup_logger()

# MODELS

class Event(BaseModel):
    sid: str
    event_name: str
    metadata: dict
    timestamp: str


class CheckRequest(BaseModel):
    sid: str
    app: str


# ENDPOINTS

@app.post("/event")
def receive_event(event: Event):
    try:
        engine.process_event(event.model_dump())
        logger.info("Event received: %s", event.model_dump())
        return {"status": "ok"}
    except Exception as exc:
        logger.exception("Failed to process event")
        raise HTTPException(status_code=400, detail=str(exc))

@app.post("/check_app")
def check_app(data: CheckRequest):
    try:
        allowed = engine.can_user_run_app(data.sid, data.app)
        
        # Get duration data for UI enhancement
        user_id = db.get_user_id_by_sid(data.sid)
        used_minutes = 0
        if user_id:
            used_today = db.get_used_time_today(user_id, data.app)
            active_time = db.get_active_session_time(user_id, data.app)
            used_minutes = used_today + active_time
            
        return {
            "allowed": allowed,
            "used_minutes": round(used_minutes, 2)
        }
    except Exception as exc:
        logger.exception("Failed to evaluate app access")
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/parent_dashboard")
def dashboard():

    result = []

    db.cursor.execute("SELECT id, name FROM users WHERE type='child'")
    users = db.cursor.fetchall()

    for user_id, name in users:

        user_data = {
            "name": name,
            "apps": []
        }

        db.cursor.execute("""
        SELECT app_name, allowed_minutes
        FROM app_rules
        WHERE user_id=%s
        """, (user_id,))

        rules = db.cursor.fetchall()

        for app_name, allowed in rules:

            used = db.get_used_time_today(user_id, app_name)
            active = db.get_active_session_time(user_id, app_name)

            total = used + active

            user_data["apps"].append({
                "app": app_name,
                "used": round(total, 2),
                "allowed": allowed
            })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

