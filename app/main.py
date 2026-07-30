import os
import traceback
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, Depends
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv

from app.core.database import SessionLocal, init_db
from app.core.state_machine import get_session, set_session_state
from app.core.llm_router import classify_intent
from app.services.crud import get_customer, create_customer, update_customer_language
from app.core.translations import t

from app.flows.pickup import handle_pickup_flow
from app.flows.status import handle_status_flow
from app.flows.pricing import handle_pricing_flow
from app.services.whatsapp_sender import send_text_message

load_dotenv()

app = FastAPI(title="Ashirwad Cleaners Agent API")

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "YOUR_CUSTOM_VERIFY_TOKEN")

@app.on_event("startup")
def on_startup():
    init_db()

def process_whatsapp_message(payload: dict):
    # This runs in the background
    try:
        # Extract basic info from Meta Payload
        entry = payload.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        
        if not messages:
            return
            
        message = messages[0]
        phone_number = message.get("from")
        
        db = SessionLocal()
        
        # 1. Check or Create Customer
        customer = get_customer(db, phone_number)
        if not customer:
            customer = create_customer(db, phone_number)
            
        lang = customer.preferred_language or "ENGLISH"

        # Working Hours Check
        from datetime import datetime, time
        from zoneinfo import ZoneInfo
        ist = ZoneInfo("Asia/Kolkata")
        now = datetime.now(ist)
        if not (time(9, 0) <= now.time() <= time(20, 30)):
            from app.services.whatsapp_sender import send_text_message
            send_text_message(phone_number, t("CLOSED_WARNING", lang))
            db.close()
            return {"status": "ok"}
        
        # Handle Interactive vs Text
        if message.get("type") == "interactive":
            interactive = message.get("interactive")
            if interactive.get("type") == "button_reply":
                text = interactive.get("button_reply", {}).get("id")
            else:
                text = "UNKNOWN_INTERACTIVE"
        elif message.get("type") == "location":
            lat = message.get("location", {}).get("latitude")
            long = message.get("location", {}).get("longitude")
            text = f"{lat},{long}"
        else:
            text = message.get("text", {}).get("body", "")
            
        # 2. Check Session
        session = get_session(phone_number)
        
        if session:
            state = session["state"]
            if state.startswith("PICKUP"):
                session["data"]["customer_id"] = customer.customer_id
                handle_pickup_flow(phone_number, text, db, session)
            elif state.startswith("PRICING"):
                handle_pricing_flow(phone_number, text, session)
            else:
                # Fallback for stuck session
                send_text_message(phone_number, t("FALLBACK_STUCK_SESSION", lang))
                from app.core.state_machine import clear_session
                clear_session(phone_number)
        else:
            # 3. No active session, Route via Gemini
            # Check for known button intents first to bypass LLM
            if text == "btn_intent_pickup":
                intent = "INTENT_PICKUP"
            elif text == "btn_intent_status":
                intent = "INTENT_STATUS"
            elif text == "btn_intent_pricing":
                intent = "INTENT_PRICING"
            else:
                intent, detected_lang = classify_intent(text)
                # Update preferred language in DB
                update_customer_language(db, customer.customer_id, detected_lang)
                customer.preferred_language = detected_lang
                lang = detected_lang
            
            if intent == "INTENT_PICKUP":
                # Start pickup flow
                session_data = {"customer_id": customer.customer_id}
                handle_pickup_flow(phone_number, text, db, {"state": "INTENT_PICKUP", "data": session_data})
            elif intent == "INTENT_STATUS":
                handle_status_flow(phone_number, text, db, customer.customer_id)
            elif intent == "INTENT_PRICING":
                handle_pricing_flow(phone_number, text, {"state": "INTENT_PRICING", "data": {}})
            else:
                from app.services.whatsapp_sender import send_interactive_buttons
                pickup_title = "Pickup" if lang == "ENGLISH" else "Pickup / Book"
                status_title = "Status" if lang == "ENGLISH" else "Status / Track"
                pricing_title = "Pricing" if lang == "ENGLISH" else "Pricing / Catalog"
                
                buttons = [
                    {"id": "btn_intent_pickup", "title": pickup_title},
                    {"id": "btn_intent_status", "title": status_title},
                    {"id": "btn_intent_pricing", "title": pricing_title}
                ]
                send_interactive_buttons(
                    phone_number, 
                    t("WELCOME_MSG", lang), 
                    buttons
                )
                
        db.close()
    except Exception as e:
        print(f"Error processing message: {e}")
        traceback.print_exc()

@app.get("/webhook")
async def verify_webhook(request: Request):
    """Handles the initial WhatsApp webhook verification ping."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return PlainTextResponse(challenge, status_code=200)
    raise HTTPException(status_code=403, detail="Invalid verification token")

@app.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    """Receives inbound messages and instantly returns 200 OK."""
    try:
        payload = await request.json()
        background_tasks.add_task(process_whatsapp_message, payload)
        return {"status": "ok"}
    except Exception as e:
        print(f"Webhook Error: {e}")
        return {"status": "error"}
