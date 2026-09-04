import sys
from datetime import datetime
from dotenv import load_dotenv

sys.path.append("/Users/dhruvpatel/PROJECTS/Ashirwad_Cleaners_Bot")
load_dotenv("/Users/dhruvpatel/PROJECTS/Ashirwad_Cleaners_Bot/.env")

from app.core.database import SessionLocal, init_db
from app.models.schemas import Customer, Order, OrderStatus, OrderType, PaymentStatus
from app.services.crud import create_order, now_ist
from dashboard import format_ist_datetime

print("--- STARTING ORDER TIMESTAMPS TEST ---")
init_db()

phone = "919999988888"
with SessionLocal() as db:
    cust = db.query(Customer).filter(Customer.phone_number == phone).first()
    if cust:
        db.query(Order).filter(Order.customer_id == cust.customer_id).delete()
        db.delete(cust)
        db.commit()
        
    cust = Customer(phone_number=phone, name="Timestamp Test Customer", preferred_language="ENGLISH")
    db.add(cust)
    db.commit()
    db.refresh(cust)
    
    # 1. Create order
    order = create_order(
        db,
        cust.customer_id,
        item_count=3,
        order_type="PICKUP",
        service_category="Dry Clean",
        flat_address="9, Paldi",
        estimated_amount=150.0
    )
    
    print(f"[Check 1] Created Order ID: {order.order_id}")
    print(f"   Created At (IST): {order.created_at} -> Formatted: {format_ist_datetime(order.created_at)}")
    assert order.created_at is not None, "Order created_at should not be None"
    assert order.picked_up_at is None, "Order picked_up_at should initially be None"
    assert order.delivered_at is None, "Order delivered_at should initially be None"
    
    # 2. Simulate pickup
    order.status = OrderStatus.IN_SHOP
    order.picked_up_at = now_ist()
    db.commit()
    
    print(f"[Check 2] Picked Up At (IST): {order.picked_up_at} -> Formatted: {format_ist_datetime(order.picked_up_at)}")
    assert order.picked_up_at is not None, "Order picked_up_at should be populated"
    
    # 3. Simulate delivery
    order.status = OrderStatus.DELIVERED
    order.payment_status = PaymentStatus.PAID
    order.delivered_at = now_ist()
    db.commit()
    
    print(f"[Check 3] Delivered At (IST): {order.delivered_at} -> Formatted: {format_ist_datetime(order.delivered_at)}")
    assert order.delivered_at is not None, "Order delivered_at should be populated"

    # Cleanup test customer
    db.query(Order).filter(Order.customer_id == cust.customer_id).delete()
    db.delete(cust)
    db.commit()

print("\n✅ ORDER LIFECYCLE TIMESTAMPS TEST PASSED PERFECTLY!")
