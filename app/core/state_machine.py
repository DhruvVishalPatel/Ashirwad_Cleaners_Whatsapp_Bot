from datetime import datetime, timedelta
import threading

# Simple in-memory session store for MVP. 
# In production, replace with Redis: redis_client.set(f"session:{phone}", state_data, ex=7200)
sessions = {}
session_lock = threading.Lock()

SESSION_TTL_MINUTES = 120

def get_session(phone_number: str) -> dict:
    with session_lock:
        session = sessions.get(phone_number)
        if session:
            # Check TTL
            if datetime.utcnow() > session['expires_at']:
                del sessions[phone_number]
                return None
            return session
        return None

def set_session_state(phone_number: str, state: str, data: dict = None):
    with session_lock:
        sessions[phone_number] = {
            "state": state,
            "data": data or {},
            "expires_at": datetime.utcnow() + timedelta(minutes=SESSION_TTL_MINUTES)
        }

def update_session_data(phone_number: str, key: str, value: any):
    with session_lock:
        if phone_number in sessions:
            sessions[phone_number]["data"][key] = value
            sessions[phone_number]["expires_at"] = datetime.utcnow() + timedelta(minutes=SESSION_TTL_MINUTES)

def clear_session(phone_number: str):
    with session_lock:
        if phone_number in sessions:
            del sessions[phone_number]
