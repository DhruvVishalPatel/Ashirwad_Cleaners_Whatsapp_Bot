from contextlib import asynccontextmanager
import os
import traceback
from datetime import datetime, time
from zoneinfo import ZoneInfo
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database schema...")
    init_db()
    logger.info("Database schema initialized successfully.")
    yield

app = FastAPI(title="Ashirwad Cleaners Agent API", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "YOUR_CUSTOM_VERIFY_TOKEN")

def process_whatsapp_message(payload: dict):
    # This runs in the background
    try:
        # Extract basic info from Meta Payload with safe checks
        entries = payload.get("entry", [])
        if not isinstance(entries, list) or not entries:
            return
            
        changes = entries[0].get("changes", [])
        if not isinstance(changes, list) or not changes:
            return
            
        value = changes[0].get("value", {})
        messages = value.get("messages", [])
        if not isinstance(messages, list) or not messages:
            return
            
        message = messages[0]
        phone_number = message.get("from")
        if not phone_number:
            return
        
        # 1. Check or Create Customer
        with SessionLocal() as db:
            customer = get_customer(db, phone_number)
            if not customer:
                customer = create_customer(db, phone_number)
                
            customer_id = customer.customer_id
            customer_name = customer.name or ""
            lang = customer.preferred_language or ""
            
        lang_for_warning = lang if lang else "ENGLISH"

        # Working Hours Check (9:00 AM to 8:30 PM IST)
        ist = ZoneInfo("Asia/Kolkata")
        now = datetime.now(ist)
        if not (time(9, 0) <= now.time() <= time(20, 30)):
            send_text_message(phone_number, t("CLOSED_WARNING", lang_for_warning))
            return
        
        # Handle Interactive vs Text vs Location
        if message.get("type") == "interactive":
            interactive = message.get("interactive", {})
            if interactive.get("type") == "button_reply":
                text = interactive.get("button_reply", {}).get("id", "")
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
                "customer_id": customer_id,
                "language": lang,
                "current_flow": "IDLE",
                "current_state": "",
                "last_active_state": "",
                "customer_name": customer_name,
                "garments_list": [],
                "item_count": 0,
                "points_redeemed": 0,
                "saved_address": "",
                "pending_items_input": "",
                "direct_order_prefix": ""
            }
            
        # Update text input and run graph
        current_state_data["text_input"] = text
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
        raise HTTPException(status_code=400, detail="Invalid payload")

