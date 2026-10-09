from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.models.schemas import Customer
from app.services.crud import (
    get_customer_chats,
    get_chat_history,
    toggle_customer_bot_pause,
    get_customer
)
from app.services.whatsapp_sender import send_text_message
from app.core.logger import logger

router = APIRouter(prefix="/chats", tags=["chat"])

class SendMessageRequest(BaseModel):
    message: str

class ToggleBotRequest(BaseModel):
    paused: bool

@router.get("")
def list_chats(db: Session = Depends(get_db)):
    """Retrieve list of all customer conversation threads with last message & bot status."""
    return get_customer_chats(db)

@router.get("/{customer_id}")
def get_chat_messages(customer_id: int, db: Session = Depends(get_db)):
    """Retrieve full message history for a specific customer."""
    return get_chat_history(db, customer_id)

@router.post("/{customer_id}/send")
def send_manager_message(customer_id: int, req: SendMessageRequest, db: Session = Depends(get_db)):
    """Send a manual WhatsApp message to a customer from Manager Faizan."""
    customer = db.query(Customer).filter_by(customer_id=customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message content cannot be empty")

    logger.info(f"Manager Faizan sending manual message to {customer.phone_number}: {req.message}")
    res = send_text_message(customer.phone_number, req.message.strip(), sender_type="MANAGER")
    return {"status": "success", "response": res}

@router.put("/{customer_id}/toggle-bot")
def toggle_bot_pause(customer_id: int, req: ToggleBotRequest, db: Session = Depends(get_db)):
    """Pause or resume automated AI Bot responses for a customer."""
    customer = toggle_customer_bot_pause(db, customer_id, req.paused)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return {
        "status": "success",
        "customer_id": customer.customer_id,
        "bot_paused": customer.bot_paused
    }
