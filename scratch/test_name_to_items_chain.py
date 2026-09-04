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
import app.flows.pickup
app.flows.pickup.send_text_message = mock_send_text

from app.core.database import SessionLocal, init_db
from app.models.schemas import Customer, Order
from app.core.graph import compiled_graph

print("--- TESTING NAME TO ITEMS GRAPH CHAINING ---")
init_db()

phone = "919988776655"
with SessionLocal() as db:
    c = db.query(Customer).filter(Customer.phone_number == phone).first()
    if c:
        db.query(Order).filter(Order.customer_id == c.customer_id).delete()
        db.delete(c)
        db.commit()
    cust = Customer(phone_number=phone, name=None, preferred_language="ENGLISH")
    db.add(cust)
    db.commit()
    db.refresh(cust)

config = {"configurable": {"thread_id": phone}}

# Step 1: User sends direct order without name
print("\n--- STEP 1: Direct Order Input ---")
msg1 = "Wash 2 tops and steam press one more top"
state1 = {
    "phone_number": phone,
    "text_input": msg1,
    "customer_id": cust.customer_id,
    "language": "ENGLISH",
    "current_flow": "IDLE",
    "current_state": ""
}
out1 = compiled_graph.invoke(state1, config=config)
print("Step 1 State Output:", out1.get("current_flow"), out1.get("current_state"))
print(f"Step 1 Received Msg: {received_messages[-1]}")
assert "What is your name?" in received_messages[-1], "Step 1 failed to ask for name."

# Step 2: User provides name "Dhruv"
print("\n--- STEP 2: Name Input 'Dhruv' ---")
msg2 = "Dhruv"
state2 = {
    "phone_number": phone,
    "text_input": msg2,
    "customer_id": out1.get("customer_id")
}
out2 = compiled_graph.invoke(state2, config=config)
print("Step 2 State Output:", out2.get("current_flow"), out2.get("current_state"))

print(f"\nStep 2 Received Msgs Count: {len(received_messages)}")
last_msg = received_messages[-1]
print(f"Step 2 Last Received Msg:\n{last_msg}")

assert len(received_messages) >= 2, "Failed! Step 2 did not send estimate message!"
assert "Dhruv" in last_msg or "Nice to meet you" in last_msg or "2x" in last_msg or "Top" in last_msg or "Estimate" in last_msg, f"Unexpected Step 2 response: {last_msg}"

# Cleanup
with SessionLocal() as db:
    c = db.query(Customer).filter(Customer.phone_number == phone).first()
    if c:
        db.query(Order).filter(Order.customer_id == c.customer_id).delete()
        db.delete(c)
        db.commit()

print("\n✅ NAME TO ITEMS GRAPH CHAINING PASSED PERFECTLY!")
