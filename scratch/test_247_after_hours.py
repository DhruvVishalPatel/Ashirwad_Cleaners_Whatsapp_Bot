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
from app.flows.pickup import pickup_address_node

print("--- STARTING 24/7 & AFTER HOURS RECEIPT TEST ---")
init_db()

phone = "919999988888"
with SessionLocal() as db:
    cust = db.query(Customer).filter(Customer.phone_number == phone).first()
    if cust:
        db.query(Order).filter(Order.customer_id == cust.customer_id).delete()
        db.delete(cust)
        db.commit()
        
    cust = Customer(phone_number=phone, name="After Hours Test", preferred_language="ENGLISH")
    db.add(cust)
    db.commit()
    db.refresh(cust)

state = {
    "phone_number": phone,
    "customer_id": cust.customer_id,
    "language": "ENGLISH",
    "text_input": "9, Sujit Apartment, Ajit Society, Paldi",
    "current_state": "PICKUP_AWAITING_CONFIRMATION_ADDRESS",
    "garments_list": [
        {"item_name": "Shirt", "service_type": "dry_clean", "quantity": 3, "service_category": "Dry Clean"},
        {"item_name": "Pant", "service_type": "washing", "quantity": 2, "service_category": "Washing"}
    ],
    "item_count": 5,
    "base_estimate": 350.0,
    "delivery_fee": 0.0,
    "final_estimate": 350.0,
    "points_redeemed": 0
}

res = pickup_address_node(state)

assert len(received_messages) > 0, "Failed! No message was sent."
last_msg = received_messages[-1]

print("Verifying order confirmation contents...")
assert "Order #" in last_msg, "Missing Order # in confirmation."
assert "3x Shirt" in last_msg, "Missing itemized breakdown (Shirt) in confirmation."
assert "2x Pant" in last_msg, "Missing itemized breakdown (Pant) in confirmation."
assert "Garments Estimate" in last_msg, "Missing Garments Estimate in confirmation."
assert "Pickup Address" in last_msg, "Missing Pickup Address in confirmation."

# Cleanup
with SessionLocal() as db:
    db.query(Order).filter(Order.customer_id == cust.customer_id).delete()
    c = db.query(Customer).filter(Customer.phone_number == phone).first()
    if c:
        db.delete(c)
    db.commit()

print("\n✅ 24/7 ORDER PLACEMENT & DETAILED RECEIPT TEST PASSED PERFECTLY!")
