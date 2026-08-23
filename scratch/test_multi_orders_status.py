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

print("--- STARTING MULTIPLE ORDERS STATUS TEST ---")
init_db()

phone = "917777777777"
with SessionLocal() as db:
    cust = db.query(Customer).filter(Customer.phone_number == phone).first()
    if cust:
        db.query(Order).filter(Order.customer_id == cust.customer_id).delete()
        db.delete(cust)
        db.commit()
        
    cust = Customer(phone_number=phone, name="Multi Order Test Customer", preferred_language="ENGLISH")
    db.add(cust)
    db.commit()
    db.refresh(cust)
    
    # Add 3 orders (including legacy "AC-1010" format)
    orders = [
        Order(order_id="1010", customer_id=cust.customer_id, item_count=3, order_type=OrderType.PICKUP, status=OrderStatus.PENDING_PICKUP, payment_status=PaymentStatus.PENDING),
        Order(order_id="AC-1016", customer_id=cust.customer_id, item_count=2, order_type=OrderType.PICKUP, status=OrderStatus.PENDING_PICKUP, payment_status=PaymentStatus.PENDING),
        Order(order_id="1017", customer_id=cust.customer_id, item_count=4, order_type=OrderType.PICKUP, status=OrderStatus.PENDING_PICKUP, payment_status=PaymentStatus.PENDING),
    ]
    for o in orders:
        db.add(o)
    db.commit()
    
    state = {
        "phone_number": phone,
        "customer_id": cust.customer_id,
        "language": "ENGLISH"
    }
    
    status_node(state)
    
    last_msg = received_messages[-1]
    print(f"\nLast Status Message:\n{last_msg}")
    
    assert "AC-" not in last_msg, f"Failed! Found 'AC-' in status message: {last_msg}"
    assert "• #1010: Pending Pickup" in last_msg, f"Expected • #1010: Pending Pickup in message"
    assert "• #1016: Pending Pickup" in last_msg, f"Expected • #1016: Pending Pickup in message"
    assert "• #1017: Pending Pickup" in last_msg, f"Expected • #1017: Pending Pickup in message"
    
    # Cleanup test customer
    db.query(Order).filter(Order.customer_id == cust.customer_id).delete()
    db.delete(cust)
    db.commit()

print("\n✅ MULTIPLE ORDERS STATUS TEST PASSED PERFECTLY!")
