import os
import traceback
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from app.core.database import SessionLocal, init_db
from app.services.crud import get_customer, create_customer
from app.core.translations import t
from app.services.whatsapp_sender import send_text_message
from app.core.graph import compiled_graph
from app.core.logger import logger

load_dotenv()

app = FastAPI(title="Ashirwad Cleaners Agent API")
app.mount("/static", StaticFiles(directory="static"), name="static")

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "YOUR_CUSTOM_VERIFY_TOKEN")

@app.on_event("startup")
def on_startup():
    logger.info("Initializing database schema...")
    init_db()
    logger.info("Database schema initialized successfully.")

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
            send_text_message(phone_number, t("CLOSED_WARNING", lang))
            db.close()
            return {"status": "ok"}
        
        db.close()  # Close DB before calling LangGraph (it opens its own connections if needed)
        
        # Handle Interactive vs Text vs Location
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
            
        # 2. RUN LANGGRAPH AGENT ENGINE
        config = {"configurable": {"thread_id": phone_number}}
        
        # Get existing thread state if any
        current_state_data = compiled_graph.get_state(config).values
        
        if not current_state_data:
            current_state_data = {
                "phone_number": phone_number,
                "customer_id": customer.customer_id,
                "language": lang,
                "current_flow": "IDLE",
                "current_state": "",
                "last_active_state": "",
                "customer_name": customer.name or "",
                "garments_list": [],
                "item_count": 0,
                "points_redeemed": 0,
                "saved_address": "",
                "pending_items_input": "",
                "direct_order_prefix": ""
            }
            
        # Update text input and run graph
        logger.info(f"Invoking StateGraph for customer_id: {current_state_data.get('customer_id')} with input: '{text}'")
        compiled_graph.invoke(current_state_data, config)
        logger.info(f"StateGraph invocation finished successfully for customer_id: {current_state_data.get('customer_id')}")
        
    except Exception as e:
        logger.error(f"Error processing message: {e}\n{traceback.format_exc()}")

@app.get("/webhook")
async def verify_webhook(request: Request):
    """Handles the initial WhatsApp webhook verification ping."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("Webhook validation ping successful!")
        return PlainTextResponse(challenge, status_code=200)
    logger.warning("Webhook validation ping failed: Invalid verification token.")
    raise HTTPException(status_code=403, detail="Invalid verification token")

@app.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    """Receives inbound messages and instantly returns 200 OK."""
    try:
        payload = await request.json()
        logger.debug(f"Webhook payload received: {payload}")
        background_tasks.add_task(process_whatsapp_message, payload)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook Endpoint Error: {e}")
        return {"status": "error"}
