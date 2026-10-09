from typing import Any, List, Dict, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.models.schemas import Customer, Order, OrderItem, Runner, PointTransaction, OrderType, ChatMessage


def get_customer(db: Session, phone_number: str):
    return db.query(Customer).filter(Customer.phone_number == phone_number).first()

def create_customer(db: Session, phone_number: str, name: str = None, preferred_language: str = "ENGLISH"):
    db_customer = Customer(
        phone_number=phone_number, 
        name=name, 
        preferred_language=preferred_language or "ENGLISH"
    )
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

def get_google_maps_url(location: Optional[str]) -> str:
    if not location or location in ["N/A", "No Location Provided"]:
        return ""
    loc = location.strip()
    if loc.startswith("http://") or loc.startswith("https://"):
        return loc
    return f"https://www.google.com/maps?q={loc}"


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
    transactions = db.query(PointTransaction).filter(
        PointTransaction.customer_id == customer_id
    ).order_by(PointTransaction.created_at.asc()).all()
    now = datetime.utcnow()
    
    buckets = []
    for t in transactions:
        if t.transaction_type == "EARNED":
            buckets.append({'amount': t.points, 'expires_at': t.expires_at})
        elif t.transaction_type == "REDEEMED":
            points_to_deduct = t.points
            for b in buckets:
                # Deduct only from buckets that were unexpired at the time of redemption
                if b['amount'] > 0 and (b['expires_at'] is None or b['expires_at'] > t.created_at):
                    deduct = min(b['amount'], points_to_deduct)
                    b['amount'] -= deduct
                    points_to_deduct -= deduct
                    if points_to_deduct == 0:
                        break
                    
    # Sum only unexpired points as of now
    available = sum(b['amount'] for b in buckets if b['amount'] > 0 and (b['expires_at'] is None or b['expires_at'] > now))
    return max(0, available)

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

def clean_order_id(order_id: Any) -> str:
    if not order_id:
        return ""
    s = str(order_id).strip()
    if s.startswith("AC-"):
        return s[3:]
    if s.startswith("AC"):
        return s[2:]
    return s

def _generate_next_order_id(db: Session) -> str:
    existing_ids = db.query(Order.order_id).all()
    max_num = 1000
    for (o_id,) in existing_ids:
        try:
            digits = ''.join(filter(str.isdigit, o_id or ""))
            if digits:
                num = int(digits)
                if num > max_num:
                    max_num = num
        except ValueError:
            pass
    return str(max_num + 1)

def now_ist() -> datetime:
    from datetime import datetime, timezone, timedelta
    return datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=5, minutes=30))).replace(tzinfo=None)

def create_order(db: Session, customer_id: int, item_count: int, order_type: str = "PICKUP", service_category: str = None, flat_address: str = None, estimated_amount: float = None, delivery_fee: float = 0.0, points_redeemed: int = 0, special_instructions: str = None, disclaimer_accepted: bool = True, garments_list: list = None):
    from sqlalchemy.exc import IntegrityError

    for _ in range(5):
        order_id = _generate_next_order_id(db)
        try:
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
                disclaimer_accepted=disclaimer_accepted,
                created_at=now_ist()
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
                
            # Broadcast real-time WebSocket event to admin dashboard
            try:
                from app.core.ws_manager import broadcast_event_sync
                broadcast_event_sync("ORDER_CREATED", {
                    "order_id": db_order.order_id,
                    "customer_id": customer_id,
                    "item_count": item_count,
                    "service_category": service_category
                })
            except Exception:
                pass

            return db_order
        except IntegrityError:
            db.rollback()
            continue

    raise RuntimeError("Failed to generate a unique order ID after 5 attempts.")

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

def log_chat_message(
    db: Session,
    customer_id: int,
    phone_number: str,
    sender_type: str,
    content: str,
    message_type: str = "text",
    media_url: str = None
) -> ChatMessage:
    msg = ChatMessage(
        customer_id=customer_id,
        phone_number=phone_number,
        sender_type=sender_type,
        message_type=message_type,
        content=content,
        media_url=media_url,
        created_at=now_ist()
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    # Broadcast real-time WS event
    try:
        from app.core.ws_manager import broadcast_event_sync
        broadcast_event_sync("CHAT_MESSAGE_RECEIVED", {
            "id": msg.id,
            "customer_id": msg.customer_id,
            "phone_number": msg.phone_number,
            "sender_type": msg.sender_type,
            "message_type": msg.message_type,
            "content": msg.content,
            "media_url": msg.media_url,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
            "created_at_formatted": msg.created_at.strftime("%I:%M %p") if msg.created_at else ""
        })
    except Exception:
        pass

    return msg

def get_customer_chats(db: Session):
    customers = db.query(Customer).all()
    chat_list = []
    for c in customers:
        last_msg = db.query(ChatMessage).filter(
            ChatMessage.customer_id == c.customer_id
        ).order_by(ChatMessage.created_at.desc()).first()

        active_orders = get_active_orders(db, c.customer_id)

        chat_list.append({
            "customer_id": c.customer_id,
            "customer_name": c.name or "Unknown",
            "phone_number": c.phone_number,
            "saved_address": c.saved_address or "",
            "last_location_gps": c.last_location_gps or "",
            "bot_paused": getattr(c, "bot_paused", False) or False,
            "has_active_order": len(active_orders) > 0,
            "active_order_id": active_orders[0].order_id if active_orders else None,
            "active_order_status": active_orders[0].status.name if active_orders else None,
            "last_message": {
                "content": last_msg.content if last_msg else "No messages yet",
                "sender_type": last_msg.sender_type if last_msg else "BOT",
                "created_at": last_msg.created_at.isoformat() if last_msg and last_msg.created_at else None,
                "created_at_formatted": last_msg.created_at.strftime("%d %b, %I:%M %p") if last_msg and last_msg.created_at else ""
            } if last_msg else None
        })

    # Sort threads by last message created_at descending
    chat_list.sort(
        key=lambda x: x["last_message"]["created_at"] if (x["last_message"] and x["last_message"]["created_at"]) else "1970-01-01",
        reverse=True
    )
    return chat_list

def get_chat_history(db: Session, customer_id: int):
    messages = db.query(ChatMessage).filter(
        ChatMessage.customer_id == customer_id
    ).order_by(ChatMessage.created_at.asc()).all()

    return [
        {
            "id": m.id,
            "customer_id": m.customer_id,
            "phone_number": m.phone_number,
            "sender_type": m.sender_type,
            "message_type": m.message_type,
            "content": m.content,
            "media_url": m.media_url,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "created_at_formatted": m.created_at.strftime("%I:%M %p") if m.created_at else ""
        }
        for m in messages
    ]

def toggle_customer_bot_pause(db: Session, customer_id: int, paused: bool):
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if customer:
        customer.bot_paused = paused
        db.commit()
        db.refresh(customer)

        try:
            from app.core.ws_manager import broadcast_event_sync
            broadcast_event_sync("CHAT_BOT_TOGGLED", {
                "customer_id": customer.customer_id,
                "bot_paused": customer.bot_paused
            })
        except Exception:
            pass

    return customer


