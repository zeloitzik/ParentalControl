from fastapi import FastAPI, Request
from pydantic import BaseModel 
from database import DatabaseManager
from engine import ServerEngine
from setup_logger import my_logger
import logging
app = FastAPI()

# init
db = DatabaseManager()
engine = ServerEngine(db.get_cursor())
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
    data = Request.get_json()
    event = Event(**data)
    engine.process_event(event.dict())
    logger.info(f"Event received: {event.dict()}")
    return {"status": "ok"}


@app.post("/check_app")
def check_app(data: CheckRequest):
    data_raw = Request.get_json()
    data = CheckRequest(**data_raw)
    allowed = engine.can_user_run_app(data.sid, data.app)
    logger.info(f"Check app request: {data.dict()}, allowed: {allowed}")
    return {
        "allowed": allowed
    }


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

        result.append(user_data)

    return result

