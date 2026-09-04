from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.schemas import Order, OrderStatus, PaymentStatus, Customer, OrderItem, CatalogItem, Runner, PointTransaction
from app.services.crud import get_monthly_order_count, add_points_transaction, now_ist, clean_order_id, get_runners
from app.services.whatsapp_sender import send_text_message

router = APIRouter(prefix="/orders", tags=["Orders"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def format_ist_datetime(dt) -> Optional[str]:
    if not dt:
        return None
    return dt.strftime("%d %b %Y, %I:%M %p")

class OrderItemSchema(BaseModel):
    item_id: Optional[int] = None
    garment_type: str
    service_type: str
    quantity: int

class UpdateOrderItemsRequest(BaseModel):
    flat_address: Optional[str] = ""
    special_instructions: Optional[str] = ""
    items: List[OrderItemSchema]

class UpdatePriceRequest(BaseModel):
    raw_price: float

class UpdateStatusRequest(BaseModel):
    payment_status: str
    status: str

class DispatchRunnerRequest(BaseModel):
    runner_phone: str

@router.get("/analytics")
def get_analytics(db: Session = Depends(get_db)):
    total_customers = db.query(Customer).count()
    active_orders_count = db.query(Order).filter(
        ~Order.status.in_([OrderStatus.DELIVERED, OrderStatus.CANCELLED, OrderStatus.REJECTED])
    ).count()
    pending_pickups = db.query(Order).filter(Order.status == OrderStatus.PENDING_PICKUP).count()

    return {
        "active_orders": active_orders_count,
        "pending_pickups": pending_pickups,
        "total_customers": total_customers
    }

def serialize_order(o: Order) -> dict:
    delivery_fee = getattr(o, "delivery_fee", 0.0) or 0.0
    points_redeemed = getattr(o, "points_redeemed", 0) or 0
    raw_est = o.estimated_amount or 0.0
    raw_total = o.total_amount if o.total_amount is not None else raw_est
    final_total = raw_total + delivery_fee - points_redeemed

    items_serialized = [
        {
            "item_id": oi.item_id,
            "garment_type": oi.garment_type,
            "service_type": oi.service_type,
            "quantity": oi.quantity
        }
        for oi in (o.items or [])
    ]

    return {
        "order_id": o.order_id,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "created_at_formatted": format_ist_datetime(o.created_at),
        "picked_up_at": o.picked_up_at.isoformat() if o.picked_up_at else None,
        "picked_up_at_formatted": format_ist_datetime(o.picked_up_at),
        "delivered_at": o.delivered_at.isoformat() if o.delivered_at else None,
        "delivered_at_formatted": format_ist_datetime(o.delivered_at),
        "order_type": o.order_type.name if o.order_type else "PICKUP",
        "service_category": o.service_category or "Dry Clean",
        "customer_id": o.customer_id,
        "customer_name": o.customer.name if o.customer and o.customer.name else "Unknown",
        "customer_phone": o.customer.phone_number if o.customer else "Unknown",
        "flat_address": o.flat_address or "",
        "last_location_gps": o.customer.last_location_gps if o.customer and o.customer.last_location_gps else "",
        "item_count": o.item_count,
        "estimated_amount": o.estimated_amount or 0.0,
        "total_amount": o.total_amount,
        "delivery_fee": delivery_fee,
        "points_redeemed": points_redeemed,
        "final_total": final_total,
        "payment_status": o.payment_status.name if o.payment_status else "PENDING",
        "status": o.status.name if o.status else "PENDING_PICKUP",
        "special_instructions": o.special_instructions or "",
        "runner_id": o.runner_id,
        "items": items_serialized
    }

@router.get("")
def list_orders(show_all: bool = Query(False), db: Session = Depends(get_db)):
    if show_all:
        orders = db.query(Order).all()
    else:
        orders = db.query(Order).filter(
            ~Order.status.in_([OrderStatus.DELIVERED, OrderStatus.CANCELLED, OrderStatus.REJECTED])
        ).all()

    return [serialize_order(o) for o in orders]

@router.get("/{order_id}")
def get_order_details(order_id: str, db: Session = Depends(get_db)):
    c_id = clean_order_id(order_id)
    order = db.query(Order).filter(Order.order_id == c_id).first()
    if not order:
        order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return serialize_order(order)

@router.put("/{order_id}/items")
def update_order_items(order_id: str, req: UpdateOrderItemsRequest, db: Session = Depends(get_db)):
    c_id = clean_order_id(order_id)
    order = db.query(Order).filter((Order.order_id == c_id) | (Order.order_id == order_id)).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.flat_address = req.flat_address
    order.special_instructions = req.special_instructions

    # Remove existing items
    db.query(OrderItem).filter(OrderItem.order_id == order.order_id).delete()

    catalog_items = db.query(CatalogItem).all()
    price_lookup = {(c.service_type, c.item_name): c.price for c in catalog_items}

    total_qty = 0
    estimated_sum = 0.0
    services_used = set()

    for item in req.items:
        oi = OrderItem(
            order_id=order.order_id,
            garment_type=item.garment_type,
            service_type=item.service_type,
            quantity=item.quantity
        )
        db.add(oi)
        total_qty += item.quantity
        services_used.add(item.service_type.replace("_", " ").title())

        item_price = price_lookup.get((item.service_type, item.garment_type), 50.0)
        estimated_sum += (item_price * item.quantity)

    order.item_count = total_qty
    order.estimated_amount = estimated_sum
    order.service_category = ", ".join(list(services_used)) if services_used else "Dry Clean"

    # Monthly delivery fee logic
    monthly_orders = get_monthly_order_count(db, order.customer_id)
    order.delivery_fee = 0.0 if monthly_orders >= 4 else 30.0

    db.commit()
    db.refresh(order)

    try:
        from app.core.ws_manager import broadcast_event_sync
        broadcast_event_sync("ORDER_UPDATED", {"order_id": order.order_id, "action": "items_updated"})
    except Exception:
        pass

    return serialize_order(order)

@router.put("/{order_id}/price")
def update_order_price(order_id: str, req: UpdatePriceRequest, db: Session = Depends(get_db)):
    c_id = clean_order_id(order_id)
    order = db.query(Order).filter((Order.order_id == c_id) | (Order.order_id == order_id)).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.total_amount = req.raw_price
    db.commit()
    db.refresh(order)

    try:
        from app.core.ws_manager import broadcast_event_sync
        broadcast_event_sync("ORDER_UPDATED", {"order_id": order.order_id, "action": "price_updated"})
    except Exception:
        pass

    return serialize_order(order)

@router.put("/{order_id}/status")
def update_order_status(order_id: str, req: UpdateStatusRequest, db: Session = Depends(get_db)):
    c_id = clean_order_id(order_id)
    order = db.query(Order).filter((Order.order_id == c_id) | (Order.order_id == order_id)).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    new_status = req.status.upper()
    new_payment = req.payment_status.upper()

    # Validations
    requires_amount = ["PROCESSING", "READY", "DELIVERED"]
    if new_status in requires_amount and (order.total_amount is None or order.total_amount <= 0):
        raise HTTPException(status_code=400, detail="Total Amount must be saved before moving to PROCESSING, READY, or DELIVERED.")

    if order.status.name == "PENDING_PICKUP" and new_status not in ["PENDING_PICKUP", "CANCELLED", "REJECTED"] and not order.runner_id:
        raise HTTPException(status_code=400, detail="A Delivery Runner must be dispatched before moving past PENDING_PICKUP.")

    if new_status == "DELIVERED" and new_payment != "PAID":
        raise HTTPException(status_code=400, detail="Cannot mark order as DELIVERED until payment status is PAID.")

    order.payment_status = getattr(PaymentStatus, new_payment)
    order.status = getattr(OrderStatus, new_status)

    if new_status in ["IN_SHOP", "PICKED_UP"] and not order.picked_up_at:
        order.picked_up_at = now_ist()
    if new_status == "DELIVERED" and not order.delivered_at:
        order.delivered_at = now_ist()

    # Award points on payment
    if new_payment == "PAID":
        awarded = db.query(PointTransaction).filter(
            PointTransaction.order_id == order.order_id,
            PointTransaction.transaction_type == "EARNED"
        ).first()
        if not awarded:
            points_earned = order.item_count * 2
            add_points_transaction(db, order.customer_id, points_earned, "EARNED", order.order_id)

    db.commit()

    # Send WhatsApp updates
    if new_status == "IN_SHOP" and order.customer and order.order_type.name == "PICKUP":
        send_text_message(order.customer.phone_number, f"Good news! Your clothes (Order #{order.order_id}) have reached our shop securely.")

    elif new_status == "READY" and order.customer:
        delivery_fee = getattr(order, "delivery_fee", 0.0) or 0.0
        points_redeemed = getattr(order, "points_redeemed", 0) or 0
        final_amount = (order.total_amount or 0.0) + delivery_fee - points_redeemed

        if order.order_type.name == "PICKUP" and order.total_amount:
            if delivery_fee == 0.0:
                amount_text = f"Total bill is ₹{final_amount} (Delivery Fee Waived!)."
            else:
                amount_text = f"Total bill is ₹{final_amount} (Includes ₹{delivery_fee} Delivery Charge)."
        elif order.total_amount:
            amount_text = f"Total bill is ₹{final_amount}."
        else:
            amount_text = ""

        send_text_message(order.customer.phone_number, f"Your clothes for Order #{order.order_id} are ready! {amount_text}\nWe will deliver them soon.")

    elif new_status == "DELIVERED" and order.customer:
        dt_created = format_ist_datetime(order.created_at) or "N/A"
        dt_del = format_ist_datetime(order.delivered_at) or "N/A"
        send_text_message(
            order.customer.phone_number,
            f"🎉 *Order #{order.order_id} Delivered!* 🎉\n\n"
            f"📅 *Order Placed*: {dt_created}\n"
            f"🚚 *Delivered At*: {dt_del}\n\n"
            f"Thank you for choosing Ashirwad Cleaners! We look forward to taking care of your garments again."
        )

    db.refresh(order)

    try:
        from app.core.ws_manager import broadcast_event_sync
        broadcast_event_sync("ORDER_UPDATED", {"order_id": order.order_id, "action": "status_updated", "status": new_status})
    except Exception:
        pass

    return serialize_order(order)

@router.post("/{order_id}/dispatch")
def dispatch_runner(order_id: str, req: DispatchRunnerRequest, db: Session = Depends(get_db)):
    c_id = clean_order_id(order_id)
    order = db.query(Order).filter((Order.order_id == c_id) | (Order.order_id == order_id)).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    runners = get_runners(db)
    runner = next((r for r in runners if r.phone_number == req.runner_phone), None)
    if not runner:
        raise HTTPException(status_code=400, detail="Selected runner not found")

    customer_phone = order.customer.phone_number if order.customer else "N/A"
    customer_name = order.customer.name if order.customer and order.customer.name else "Unknown"
    location = order.customer.last_location_gps if order.customer and order.customer.last_location_gps else "No Location Provided"
    maps_link = f"https://www.google.com/maps?q={location}" if location != "No Location Provided" else "No link available."
    action = 'PICKUP' if order.status.name == 'PENDING_PICKUP' else 'DELIVERY'

    delivery_fee = getattr(order, "delivery_fee", 0.0) or 0.0
    points_redeemed = getattr(order, "points_redeemed", 0) or 0

    if action == 'PICKUP':
        est_raw = order.estimated_amount or 0.0
        est_final = est_raw + delivery_fee - points_redeemed
        amount_display = f"TBD (Estimate: ₹{est_final})"
    else:
        final_total = (order.total_amount or 0.0) + delivery_fee - points_redeemed
        amount_display = f"₹{final_total}"

    dispatch_msg = (
        f"🚨 *NEW DISPATCH: {order.order_id}* 🚨\n\n"
        f"Action: {action}\n"
        f"Service: {order.service_category or 'Dry Clean'}\n"
        f"Customer: {customer_name} ({customer_phone})\n"
        f"Items: {order.item_count}\n"
        f"Instructions: {order.special_instructions or 'None'}\n"
        f"Flat Address: {order.flat_address or 'N/A'}\n"
        f"Location: {maps_link}\n"
        f"Amount to Collect: {amount_display}"
    )

    resp = send_text_message(req.runner_phone, dispatch_msg)
    if not order.runner_id:
        order.runner_id = runner.runner_id
        db.commit()

    return {"message": f"Dispatch sent to {runner.name}", "response": resp}

@router.post("/{order_id}/reject")
def reject_order(order_id: str, db: Session = Depends(get_db)):
    c_id = clean_order_id(order_id)
    order = db.query(Order).filter((Order.order_id == c_id) | (Order.order_id == order_id)).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.status = OrderStatus.REJECTED
    db.commit()

    if order.customer:
        send_text_message(
            order.customer.phone_number,
            f"We are sorry, but we currently only offer pickup and delivery within the Paldi area. Your pickup request (Order #{order.order_id}) has been rejected. However, you are always welcome to drop off your clothes at our shop!"
        )

    return {"message": "Order rejected successfully"}

@router.post("/{order_id}/cancel")
def cancel_order(order_id: str, db: Session = Depends(get_db)):
    c_id = clean_order_id(order_id)
    order = db.query(Order).filter((Order.order_id == c_id) | (Order.order_id == order_id)).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.status = OrderStatus.CANCELLED
    db.commit()

    if order.customer:
        send_text_message(
            order.customer.phone_number,
            f"Your pickup request (Order #{order.order_id}) has been cancelled."
        )

    return {"message": "Order cancelled successfully"}
