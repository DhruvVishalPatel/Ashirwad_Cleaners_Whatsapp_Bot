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
    btn_labels = [b["title"] for b in buttons]
    print(f"📱 [WhatsApp Buttons] -> To: {to}\nMessage: {text}\nButtons: {btn_labels}")
    return {"status": "mocked"}

app.services.whatsapp_sender.send_text_message = mock_send_text
app.services.whatsapp_sender.send_interactive_buttons = mock_send_buttons

from app.core.database import SessionLocal, init_db
from app.models.schemas import Customer, Order
from app.core.graph import compiled_graph

print("--- STARTING NEW CUSTOMER DIRECT ORDER TEST ---")
init_db()

db = SessionLocal()
phone = "919999999999" # Brand new test number

# Delete existing test customer and their orders to guarantee clean slate
customer = db.query(Customer).filter(Customer.phone_number == phone).first()
if customer:
    for o in db.query(Order).filter(Order.customer_id == customer.customer_id).all():
        db.delete(o)
    db.delete(customer)
    db.commit()

# Simulate app/main.py creating the new customer record with name = None
customer = Customer(phone_number=phone, name=None, preferred_language="ENGLISH")
db.add(customer)
db.commit()
db.refresh(customer)
customer_id = customer.customer_id
db.close()

state = {
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

# Step 1: Send a direct order list as a brand new customer
send_chat("3 shirts dry clean, 2 pants washing")

# Step 2: Customer replies with their name
send_chat("Dhruv New Customer")

# Step 3: Accept estimate & points check (points is 0 for new customer, so goes to address prompt)
send_chat("paldi building flat A2")

# Verify database state
db = SessionLocal()
db_customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
print(f"\nSaved customer name in database: '{db_customer.name}'")
orders = db.query(Order).filter(Order.customer_id == customer_id).all()
print(f"Total orders created in database: {len(orders)}")
for o in orders:
    print(f"Order #{o.order_id}: Address='{o.flat_address}', Status={o.status}")
db.close()
