import os
import sys
import time
from dotenv import load_dotenv

sys.path.append("/Users/dhruvpatel/PROJECTS/Ashirwad_Cleaners_Bot")
load_dotenv("/Users/dhruvpatel/PROJECTS/Ashirwad_Cleaners_Bot/.env")

import app.services.whatsapp_sender

# Mock whatsapp sender to trace outputs
def mock_send_text(to, text):
    print(f"📱 [WhatsApp Text] -> To: {to}\nMessage: {text}")
    return {"status": "mocked"}

def mock_send_buttons(to, text, buttons):
    btn_labels = [f"{b['title']} (ID={b['id']})" for b in buttons]
    print(f"📱 [WhatsApp Buttons] -> To: {to}\nMessage: {text}\nButtons: {btn_labels}")
    return {"status": "mocked"}

def mock_send_image(to, url, caption):
    print(f"📱 [WhatsApp Image] -> To: {to}\nURL: {url}\nCaption: {caption}")
    return {"status": "mocked"}

app.services.whatsapp_sender.send_text_message = mock_send_text
app.services.whatsapp_sender.send_interactive_buttons = mock_send_buttons
app.services.whatsapp_sender.send_image_message = mock_send_image

from app.core.database import SessionLocal, init_db
from app.models.schemas import Customer, Order
from app.core.graph import compiled_graph

print("--- STARTING EXPLICIT LANGUAGE SELECTION TEST ---")
init_db()

db = SessionLocal()
phone = "918888888888" # Explicit test number

# Delete existing test customer to guarantee clean slate
customer = db.query(Customer).filter(Customer.phone_number == phone).first()
if customer:
    db.delete(customer)
    db.commit()

# Simulate app/main.py creating the new customer record with preferred_language = None
customer = Customer(phone_number=phone, name="Dhruv Lang Test", preferred_language=None)
db.add(customer)
db.commit()
db.refresh(customer)
customer_id = customer.customer_id
db.close()

state = {
    "phone_number": phone,
    "customer_id": customer_id,
    "language": "", # Starts unspecified
    "current_flow": "IDLE",
    "current_state": "",
    "last_active_state": "",
    "customer_name": "Dhruv Lang Test",
    "garments_list": [],
    "item_count": 0,
    "points_redeemed": 0,
    "saved_address": "",
    "pending_items_input": "",
    "direct_order_prefix": ""
}

config = {"configurable": {"thread_id": phone}}

def send_chat(msg: str):
    global state
    print(f"\n👤 [User]: {msg}")
    
    current_state_data = compiled_graph.get_state(config).values
    if not current_state_data:
        current_state_data = state
        
    current_state_data["text_input"] = msg
    compiled_graph.invoke(current_state_data, config)
    time.sleep(2)

# Step 1: Send "Hi" as brand new user (no language set)
# Expected: Receives combined multi-language prompt with English, Hinglish, Gujlish buttons
send_chat("Hi")

# Step 2: Click Hinglish button
# Expected: Language updated to HINGLISH, and welcome greeting with options sent immediately in HINGLISH
send_chat("btn_lang_hinglish")

# Verify database state has HINGLISH set
db = SessionLocal()
db_customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
print(f"\n[Verification] Saved language in database: '{db_customer.preferred_language}'")
db.close()

# Step 3: Send "hi" again as returning customer
# Expected: Goes directly to HINGLISH welcome greeting menu (doesn't ask for language)
send_chat("hi")

# Step 4: Send request to change language
# Expected: Language selection prompt buttons sent again
send_chat("change language")

# Step 5: Click Gujlish button
# Expected: Language updated to GUJLISH, and welcome greeting with options sent immediately in GUJLISH
send_chat("btn_lang_gujlish")

# Verify database state has GUJLISH set
db = SessionLocal()
db_customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
print(f"\n[Verification] Saved language in database: '{db_customer.preferred_language}'")
db.close()
