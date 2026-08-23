import os
os.environ["WA_ACCESS_TOKEN"] = ""
import sys
from dotenv import load_dotenv

sys.path.append("/Users/dhruvpatel/PROJECTS/Ashirwad_Cleaners_Bot")
load_dotenv("/Users/dhruvpatel/PROJECTS/Ashirwad_Cleaners_Bot/.env", override=False)

import app.services.whatsapp_sender

received_messages = []

def mock_send_text(to, text):
    print(f"📱 [WhatsApp Text] -> To: {to}\nMessage: {text}")
    received_messages.append(text)
    return {"status": "mocked"}

def mock_send_buttons(to, text, buttons):
    btn_labels = [f"{b['title']} (ID={b['id']})" for b in buttons]
    print(f"📱 [WhatsApp Buttons] -> To: {to}\nMessage: {text}\nButtons: {btn_labels}")
    received_messages.append(text)
    return {"status": "mocked"}

app.services.whatsapp_sender.send_text_message = mock_send_text
app.services.whatsapp_sender.send_interactive_buttons = mock_send_buttons

import app.flows.pickup
app.flows.pickup.send_text_message = mock_send_text
app.flows.pickup.send_interactive_buttons = mock_send_buttons

from app.core.database import SessionLocal, init_db
from app.models.schemas import Customer, Order
from app.core.graph import compiled_graph

from app.core.database import SessionLocal, init_db
from app.models.schemas import Customer, Order
from app.core.graph import compiled_graph

print("--- STARTING NAME COLLECTION FLOW TEST ---")
init_db()

phone = "911111114444"
with SessionLocal() as db:
    cust = db.query(Customer).filter(Customer.phone_number == phone).first()
    if cust:
        db.query(Order).filter(Order.customer_id == cust.customer_id).delete()
        db.delete(cust)
        db.commit()
    cust = Customer(phone_number=phone, name=None, preferred_language="ENGLISH")
    db.add(cust)
    db.commit()
    db.refresh(cust)
    customer_id = cust.customer_id

config = {"configurable": {"thread_id": phone}}

def send_chat(msg: str):
    print(f"\n👤 [User]: {msg}")
    current_state_data = compiled_graph.get_state(config).values
    if not current_state_data:
        current_state_data = {
            "phone_number": phone,
            "customer_id": customer_id,
            "language": "ENGLISH",
            "current_flow": "IDLE",
            "current_state": "",
            "last_active_state": "",
            "customer_name": "",
            "garments_list": [],
            "item_count": 0,
            "points_redeemed": 0,
            "saved_address": "",
            "pending_items_input": "",
            "direct_order_prefix": ""
        }
    current_state_data["text_input"] = msg
    compiled_graph.invoke(current_state_data, config)

# Step 1: Send "Schedule Pickup"
send_chat("Schedule Pickup")
state1 = compiled_graph.get_state(config).values
print(f"[Check 1] Flow: {state1.get('current_flow')}, State: {state1.get('current_state')}")
assert state1.get("current_state") == "PICKUP_AWAITING_NAME", f"Expected PICKUP_AWAITING_NAME, got {state1.get('current_state')}"

# Step 2: Send Name "Dhruv Patel"
send_chat("Dhruv Patel")
state2 = compiled_graph.get_state(config).values
print(f"[Check 2] Flow: {state2.get('current_flow')}, State: {state2.get('current_state')}, Name: {state2.get('customer_name')}")
assert state2.get("current_flow") == "PICKUP", f"Expected PICKUP flow, got {state2.get('current_flow')}"
assert state2.get("current_state") == "PICKUP_AWAITING_ITEMS", f"Expected PICKUP_AWAITING_ITEMS, got {state2.get('current_state')}"
assert state2.get("customer_name") == "Dhruv Patel", f"Expected customer_name 'Dhruv Patel', got {state2.get('customer_name')}"
assert "Welcome to Ashirwad Cleaners" not in received_messages[-1], "Failed! Welcome greeting was incorrectly repeated when providing name!"
print(f"All received messages: {received_messages}")
with SessionLocal() as db:
    saved_cust = db.query(Customer).filter(Customer.phone_number == phone).first()
    print(f"[Check DB] Saved Customer Name in Database: '{saved_cust.name if saved_cust else None}'")
    assert saved_cust and saved_cust.name == "Dhruv Patel", f"Expected customer name 'Dhruv Patel' in DB, got '{saved_cust.name if saved_cust else None}'"
    db.query(Order).filter(Order.customer_id == saved_cust.customer_id).delete()
    db.delete(saved_cust)
    db.commit()

print("\n✅ NAME COLLECTION FLOW TEST PASSED PERFECTLY!")
