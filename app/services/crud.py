from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.models.schemas import Customer, Order, OrderItem, Runner, PointTransaction, OrderType

def get_customer(db: Session, phone_number: str):
    return db.query(Customer).filter(Customer.phone_number == phone_number).first()

def create_customer(db: Session, phone_number: str, name: str = None):
    db_customer = Customer(phone_number=phone_number, name=name)
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)
    return db_customer

def update_customer_name(db: Session, customer_id: int, name: str):
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if customer:
        customer.name = name
        db.commit()
        db.refresh(customer)
    return customer

def update_customer_location(db: Session, customer_id: int, lat_long: str):
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if customer:
        customer.last_location_gps = lat_long
        db.commit()

def update_customer_saved_address(db: Session, customer_id: int, address: str):
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if customer:
        customer.saved_address = address
        db.commit()

def get_customer_saved_address(db: Session, customer_id: int):
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    return customer.saved_address if customer else None

def get_active_orders(db: Session, customer_id: int):
    # Active orders are ones that aren't delivered, cancelled, or rejected
    from app.models.schemas import OrderStatus
    return db.query(Order).filter(
        Order.customer_id == customer_id, 
        ~Order.status.in_([OrderStatus.DELIVERED, OrderStatus.CANCELLED, OrderStatus.REJECTED])
    ).all()

def get_monthly_order_count(db: Session, customer_id: int):
    now = datetime.utcnow()
    start_of_month = datetime(now.year, now.month, 1)
    return db.query(Order).filter(
        Order.customer_id == customer_id,
        Order.created_at >= start_of_month
    ).count()

def get_available_points(db: Session, customer_id: int) -> int:
    transactions = db.query(PointTransaction).filter(PointTransaction.customer_id == customer_id).order_by(PointTransaction.created_at.asc()).all()
    now = datetime.utcnow()
    
    buckets = []
    for t in transactions:
        if t.transaction_type == "EARNED":
            buckets.append({'amount': t.points, 'expires_at': t.expires_at})
        elif t.transaction_type == "REDEEMED":
            points_to_deduct = t.points
            for b in buckets:
                if b['amount'] > 0:
                    deduct = min(b['amount'], points_to_deduct)
                    b['amount'] -= deduct
                    points_to_deduct -= deduct
                if points_to_deduct == 0:
                    break
                    
    # Sum only unexpired points
    available = sum(b['amount'] for b in buckets if b['amount'] > 0 and b['expires_at'] > now)
    return available

def add_points_transaction(db: Session, customer_id: int, points: int, transaction_type: str, order_id: str = None):
    expires_at = None
    if transaction_type == "EARNED":
        expires_at = datetime.utcnow() + timedelta(days=90)
        
    pt = PointTransaction(
        customer_id=customer_id,
        order_id=order_id,
        points=points,
        transaction_type=transaction_type,
        expires_at=expires_at
    )
    db.add(pt)
    db.commit()

def create_order(db: Session, customer_id: int, item_count: int, order_type: str = "PICKUP", service_category: str = None, flat_address: str = None, estimated_amount: float = None, delivery_fee: float = 0.0, points_redeemed: int = 0, special_instructions: str = None, disclaimer_accepted: bool = True, garments_list: list = None):
    # Generate ID based on row count
    count = db.query(Order).count()
    order_id = f"AC-{1001 + count}"
    
    db_order = Order(
        order_id=order_id,
        customer_id=customer_id,
        item_count=item_count,
        order_type=OrderType[order_type],
        service_category=service_category,
        flat_address=flat_address,
        estimated_amount=estimated_amount,
        delivery_fee=delivery_fee,
        points_redeemed=points_redeemed,
        special_instructions=special_instructions,
        disclaimer_accepted=disclaimer_accepted
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    
    # Add OrderItems if provided
    if garments_list:
        for item in garments_list:
            oi = OrderItem(
                order_id=db_order.order_id,
                garment_type=item.get("normalized_name", "Unknown"),
                service_type=item.get("service_category", "Dry Clean"),
                quantity=item.get("quantity", 1)
            )
            db.add(oi)
        db.commit()
    
    # If points were redeemed, log the transaction
    if points_redeemed > 0:
        add_points_transaction(db, customer_id, points_redeemed, "REDEEMED", db_order.order_id)
        
    return db_order

def get_runners(db: Session):
    return db.query(Runner).all()

def create_runner(db: Session, name: str, phone_number: str):
    runner = Runner(name=name, phone_number=phone_number)
    db.add(runner)
    db.commit()
    db.refresh(runner)
    return runner

def update_customer_language(db: Session, customer_id: int, language: str):
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if customer:
        customer.preferred_language = language
        db.commit()
        db.refresh(customer)
    return customer

