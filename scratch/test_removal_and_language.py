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

print("--- STARTING REMOVAL AND LANGUAGE PERSISTENCE TEST ---")
init_db()

phone = "916666666666"
with SessionLocal() as db:
    cust = db.query(Customer).filter(Customer.phone_number == phone).first()
    if cust:
        db.delete(cust)
        db.commit()
    cust = Customer(phone_number=phone, name="Dhruv Removal Test", saved_address="9, Sujit Apartment, Ajit Society, Paldi.", preferred_language="ENGLISH")
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
            "customer_name": "Dhruv Removal Test",
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
state1 = compiled_graph.get_state(config).values
print(f"[Check 1] Count: {state1.get('item_count')}, Lang: {state1.get('language')}")

# Step 2: Send "add 3 pants for wash"
send_chat("add 3 pants for wash")
state2 = compiled_graph.get_state(config).values
print(f"[Check 2] Count: {state2.get('item_count')}, Lang: {state2.get('language')}")

# Step 3: Send "remove 4 pants from wash" (removes pants washing category)
send_chat("remove 4 pants from wash")
state3 = compiled_graph.get_state(config).values
print(f"[Check 3] Count: {state3.get('item_count')}, Lang: {state3.get('language')}")
assert state3.get("item_count") == 5, f"Expected 5 items after removal, got {state3.get('item_count')}"

# Step 4: Send "remove 2 shirts" (subtracts 2 from 5 shirts -> 3 shirts remaining)
send_chat("remove 2 shirts")
state4 = compiled_graph.get_state(config).values
print(f"[Check 4] Count: {state4.get('item_count')}, Base Estimate: {state4.get('base_estimate')}, Garments: {state4.get('garments_list')}")
assert state4.get("item_count") == 3, f"Expected 3 items remaining, got {state4.get('item_count')}"
assert state4.get("base_estimate") == 150.0, f"Expected estimate 150.0, got {state4.get('base_estimate')}"

print("\n✅ REMOVAL AND QUANTITY SUBTRACTION TEST PASSED PERFECTLY!")
