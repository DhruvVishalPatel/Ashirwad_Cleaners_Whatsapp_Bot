import sys
from datetime import datetime, timedelta

sys.path.append("/Users/dhruvpatel/PROJECTS/Ashirwad_Cleaners_Bot")

from app.core.database import SessionLocal, init_db
from app.models.schemas import Customer, PointTransaction, Order
from app.services.crud import get_available_points, add_points_transaction, create_order

print("--- TESTING POINTS FIFO CALCULATION & ORDER CREATION ---")
init_db()

with SessionLocal() as db:
    phone = "919999999999"
    # Clean up old test user
    cust = db.query(Customer).filter(Customer.phone_number == phone).first()
    if cust:
        db.query(PointTransaction).filter(PointTransaction.customer_id == cust.customer_id).delete()
        db.query(Order).filter(Order.customer_id == cust.customer_id).delete()
        db.delete(cust)
        db.commit()
        
    # Create test customer
    cust = Customer(phone_number=phone, name="Points Test User")
    db.add(cust)
    db.commit()
    db.refresh(cust)
    customer_id = cust.customer_id

    # Test Scenario 1: Earn 60 points 100 days ago (Expired)
    old_date = datetime.utcnow() - timedelta(days=100)
    pt1 = PointTransaction(
        customer_id=customer_id,
        order_id="AC-OLD1",
        points=60,
        transaction_type="EARNED",
        expires_at=datetime.utcnow() - timedelta(days=10),
        created_at=old_date
    )
    db.add(pt1)
    
    # Earn 100 points 10 days ago (Active, expires in 80 days)
    recent_date = datetime.utcnow() - timedelta(days=10)
    pt2 = PointTransaction(
        customer_id=customer_id,
        order_id="AC-NEW1",
        points=100,
        transaction_type="EARNED",
        expires_at=datetime.utcnow() + timedelta(days=80),
        created_at=recent_date
    )
    db.add(pt2)
    db.commit()

    avail1 = get_available_points(db, customer_id)
    print(f"[Test 1] Available active points (expected 100): {avail1}")
    assert avail1 == 100, f"Expected 100, got {avail1}"

    # Redeem 30 points now
    add_points_transaction(db, customer_id, 30, "REDEEMED", "AC-REDEEM1")
    avail2 = get_available_points(db, customer_id)
    print(f"[Test 2] Available active points after redeeming 30 (expected 70): {avail2}")
    assert avail2 == 70, f"Expected 70, got {avail2}"

    # Test Scenario 2: Create Order safely
    order = create_order(
        db=db,
        customer_id=customer_id,
        item_count=3,
        order_type="PICKUP",
        service_category="Dry Clean",
        flat_address="Paldi, Ahmedabad",
        estimated_amount=450.0,
        delivery_fee=0.0,
        points_redeemed=0
    )
    print(f"[Test 3] Order Created Successfully with ID: {order.order_id}")
    assert order.order_id.startswith("AC-"), f"Invalid order id format: {order.order_id}"

print("✅ ALL TESTS PASSED SUCCESSFULLY!")
