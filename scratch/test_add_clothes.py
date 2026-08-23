import sys
import time
from dotenv import load_dotenv

sys.path.append("/Users/dhruvpatel/PROJECTS/Ashirwad_Cleaners_Bot")
load_dotenv("/Users/dhruvpatel/PROJECTS/Ashirwad_Cleaners_Bot/.env")

import app.services.whatsapp_sender

def mock_send_text(to, text):
    print(f"📱 [WhatsApp Text] -> To: {to}\nMessage: {text}")
    return {"status": "mocked"}

def mock_send_buttons(to, text, buttons):
    btn_labels = [f"{b['title']} (ID={b['id']})" for b in buttons]
    print(f"📱 [WhatsApp Buttons] -> To: {to}\nMessage: {text}\nButtons: {btn_labels}")
    return {"status": "mocked"}

app.services.whatsapp_sender.send_text_message = mock_send_text
app.services.whatsapp_sender.send_interactive_buttons = mock_send_buttons

from app.core.database import SessionLocal, init_db
from app.models.schemas import Customer
from app.core.graph import compiled_graph

print("--- STARTING ADD CLOTHES SCENARIO TEST ---")
init_db()

phone = "917777777777"
with SessionLocal() as db:
    cust = db.query(Customer).filter(Customer.phone_number == phone).first()
    if cust:
        db.delete(cust)
        db.commit()
    cust = Customer(phone_number=phone, name="Dhruv Add Test", saved_address="9, Sujit Apartment, Ajit Society, Paldi.", preferred_language="ENGLISH")
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
            "customer_name": "Dhruv Add Test",
            "garments_list": [],
            "item_count": 0,
            "points_redeemed": 0,
            "saved_address": "9, Sujit Apartment, Ajit Society, Paldi.",
            "pending_items_input": "",
            "direct_order_prefix": ""
        }
    current_state_data["text_input"] = msg
    compiled_graph.invoke(current_state_data, config)

# Step 1: Send "5 shirts dry clean"
send_chat("5 shirts dry clean")

# Verify state after step 1
state_after_1 = compiled_graph.get_state(config).values
print(f"[State check 1] Flow: {state_after_1.get('current_flow')}, State: {state_after_1.get('current_state')}, Garments: {state_after_1.get('garments_list')}")

# Step 2: Send "add 3 pants for wash"
send_chat("add 3 pants for wash")

# Verify state after step 2
state_after_2 = compiled_graph.get_state(config).values
print(f"[State check 2] Total count: {state_after_2.get('item_count')}, Garments: {state_after_2.get('garments_list')}")

assert state_after_2.get("item_count") == 8, f"Expected 8 items total, got {state_after_2.get('item_count')}"
print("\n✅ TEST PASSED PERFECTLY!")
