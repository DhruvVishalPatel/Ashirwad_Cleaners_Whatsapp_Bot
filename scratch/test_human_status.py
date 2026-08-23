import sys
from dotenv import load_dotenv

sys.path.append("/Users/dhruvpatel/PROJECTS/Ashirwad_Cleaners_Bot")
load_dotenv("/Users/dhruvpatel/PROJECTS/Ashirwad_Cleaners_Bot/.env")

import app.services.whatsapp_sender

received_messages = []

def mock_send_text(to, text):
    print(f"📱 [WhatsApp Text] -> To: {to}\nMessage: {text}")
    received_messages.append(text)
    return {"status": "mocked"}

app.services.whatsapp_sender.send_text_message = mock_send_text

from app.core.database import SessionLocal, init_db
from app.models.schemas import Customer, Order, OrderStatus, OrderType, PaymentStatus
from app.flows.status import status_node

print("--- STARTING HUMAN STATUS FORMATTING TEST ---")
init_db()

phone = "918888888888"
with SessionLocal() as db:
    cust = db.query(Customer).filter(Customer.phone_number == phone).first()
    if cust:
        db.query(Order).filter(Order.customer_id == cust.customer_id).delete()
        db.delete(cust)
        db.commit()
    cust = Customer(phone_number=phone, name="Status Test Customer", preferred_language="ENGLISH")
    db.add(cust)
    db.commit()
    db.refresh(cust)
    
    order = Order(
        order_id="AC-9999",
        customer_id=cust.customer_id,
        item_count=5,
        order_type=OrderType.PICKUP,
        status=OrderStatus.PENDING_PICKUP,
        payment_status=PaymentStatus.PENDING
    )
    db.add(order)
    db.commit()
    
    state = {
        "phone_number": phone,
        "customer_id": cust.customer_id,
        "language": "ENGLISH"
    }
    
    status_node(state)
    
    last_msg = received_messages[-1]
    print(f"Last Status Message: {last_msg}")
    
    assert "PENDING_PICKUP" not in last_msg, "Failed! Raw snake_case 'PENDING_PICKUP' found in status message."
    assert "Pending Pickup" in last_msg, "Failed! Expected clean title case 'Pending Pickup'."
    
    print("\n✅ HUMAN STATUS FORMATTING TEST PASSED PERFECTLY!")
