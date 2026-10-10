from contextlib import asynccontextmanager
import os
import traceback
from datetime import datetime, time
from zoneinfo import ZoneInfo
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import PlainTextResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from app.core.database import SessionLocal, init_db
from app.services.crud import get_customer, create_customer, log_chat_message
from app.core.translations import t
from app.services.whatsapp_sender import send_text_message
from app.core.graph import compiled_graph
from app.core.logger import logger

from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database schema...")
    init_db()
    logger.info("Database schema initialized successfully.")
    yield

app = FastAPI(title="Ashirwad Cleaners Agent API", lifespan=lifespan)

# Configure CORS for local development and production admin access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

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
        
        msg_type = message.get("type", "text")

        # Handle Interactive vs Text vs Location
        if msg_type == "interactive":
            interactive = message.get("interactive", {})
            if interactive.get("type") == "button_reply":
                text = interactive.get("button_reply", {}).get("id", "")
            else:
                text = "UNKNOWN_INTERACTIVE"
        elif msg_type == "location":
            lat = message.get("location", {}).get("latitude")
            long = message.get("location", {}).get("longitude")
            text = f"{lat},{long}"
        else:
            text = message.get("text", {}).get("body", "")

        # 1. Check or Create Customer
        with SessionLocal() as db:
            customer = get_customer(db, phone_number)
            if not customer:
                customer = create_customer(db, phone_number)
                
            customer_id = customer.customer_id
            customer_name = customer.name or ""
            lang = customer.preferred_language or ""
            bot_paused = getattr(customer, "bot_paused", False) or False

            # Log inbound customer message to chat_messages
            log_chat_message(
                db,
                customer_id=customer_id,
                phone_number=phone_number,
                sender_type="CUSTOMER",
                content=text if text else f"[{msg_type.upper()} MESSAGE]",
                message_type=msg_type
            )
            
        if bot_paused:
            logger.info(f"Bot AI is paused for customer {phone_number} ({customer_name}). Skipping auto reply.")
            return

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

@app.get("/admin")
async def admin_redirect():
    return RedirectResponse(url="/")

@app.get("/chat")
@app.get("/chat/")
@app.get("/chat/{full_path:path}")
async def chat_spa_page():
    if os.path.exists("frontend/dist/index.html"):
        response = FileResponse("frontend/dist/index.html")
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    return RedirectResponse(url="/")

# Mount built frontend at bottom so explicit API & Webhook routes take precedence
if os.path.exists("frontend/dist"):
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend_root")



