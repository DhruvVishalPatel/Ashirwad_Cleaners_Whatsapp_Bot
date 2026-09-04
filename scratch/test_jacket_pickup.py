import sys
from dotenv import load_dotenv

sys.path.append("/Users/dhruvpatel/PROJECTS/Ashirwad_Cleaners_Bot")
load_dotenv("/Users/dhruvpatel/PROJECTS/Ashirwad_Cleaners_Bot/.env")

import app.services.whatsapp_sender

received_messages = []

def mock_send_text(to, text):
    print(f"📱 [WhatsApp Text] -> To: {to}\nMessage:\n{text}\n" + "-"*40)
    received_messages.append(text)
    return {"status": "mocked"}

app.services.whatsapp_sender.send_text_message = mock_send_text

from app.core.database import SessionLocal, init_db
from app.models.schemas import Customer, Order
from app.flows.pickup import pickup_items_node

print("--- TESTING JACKET PICKUP INPUTS ---")
init_db()

phone = "917600500712"
with SessionLocal() as db:
    cust = db.query(Customer).filter(Customer.phone_number == phone).first()
    if cust:
        db.query(Order).filter(Order.customer_id == cust.customer_id).delete()
        db.delete(cust)
        db.commit()
        
    cust = Customer(phone_number=phone, name="Shlok Thakkar", preferred_language="ENGLISH")
    db.add(cust)
    db.commit()
    db.refresh(cust)

# Test 1: "jacket petrol wash"
state1 = {
    "phone_number": phone,
    "customer_id": cust.customer_id,
    "language": "ENGLISH",
    "text_input": "jacket petrol wash",
    "current_flow": "PICKUP",
    "current_state": "PICKUP_AWAITING_ITEMS",
    "garments_list": []
}

res1 = pickup_items_node(state1)
print(f"Res 1 state updates: {res1}")

last_msg1 = received_messages[-1]
assert "When you're ready" not in last_msg1, f"Failed! Got fallback question loop for 'jacket petrol wash': {last_msg1}"
assert "1 items" in last_msg1 or "Jacket" in last_msg1, f"Failed to extract jacket in msg: {last_msg1}"

# Test 2: "jacket"
state2 = {
    "phone_number": phone,
    "customer_id": cust.customer_id,
    "language": "ENGLISH",
    "text_input": "jacket",
    "current_flow": "PICKUP",
    "current_state": "PICKUP_AWAITING_ITEMS",
    "garments_list": []
}

res2 = pickup_items_node(state2)
print(f"Res 2 state updates: {res2}")

last_msg2 = received_messages[-1]
assert "When you're ready" not in last_msg2, f"Failed! Got fallback question loop for 'jacket': {last_msg2}"
assert "1 items" in last_msg2 or "Jacket" in last_msg2, f"Failed to extract jacket in msg: {last_msg2}"

# Cleanup
with SessionLocal() as db:
    db.query(Order).filter(Order.customer_id == cust.customer_id).delete()
    c = db.query(Customer).filter(Customer.phone_number == phone).first()
    if c:
        db.delete(c)
    db.commit()

print("\n✅ JACKET PICKUP TEST PASSED PERFECTLY!")
