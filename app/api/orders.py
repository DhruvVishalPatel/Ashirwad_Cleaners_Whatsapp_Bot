from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import SessionLocal
from app.models.schemas import (
    Order, OrderStatus, PaymentStatus, Customer, OrderItem,
    CatalogItem, Runner, PointTransaction, OrderType, PaymentMode
)
from app.services.crud import get_monthly_order_count, add_points_transaction, now_ist, clean_order_id, get_runners
from app.services.whatsapp_sender import send_text_message
from app.core.logger import logger

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

@router.get("/analytics/detailed")
def get_detailed_analytics(
    timeframe: str = Query("weekly", description="Timeframe filter: daily, weekly, monthly, quarterly, annual, all"),
    db: Session = Depends(get_db)
):
    current_time = now_ist()
    timeframe = (timeframe or "weekly").lower()

    if timeframe == "daily":
        start_date = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        period_label = "Today"
    elif timeframe == "weekly":
        start_date = (current_time - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
        period_label = "Last 7 Days"
    elif timeframe == "monthly":
        start_date = (current_time - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
        period_label = "Last 30 Days"
    elif timeframe == "quarterly":
        start_date = (current_time - timedelta(days=90)).replace(hour=0, minute=0, second=0, microsecond=0)
        period_label = "Last 90 Days"
    elif timeframe == "annual":
        start_date = (current_time - timedelta(days=365)).replace(hour=0, minute=0, second=0, microsecond=0)
        period_label = "Last 365 Days"
    else:
        timeframe = "all"
        start_date = None
        period_label = "All Time"

    query = db.query(Order)
    if start_date:
        query = query.filter(Order.created_at >= start_date)
    orders = query.all()

    total_orders = len(orders)
    total_revenue = 0.0
    paid_revenue = 0.0
    pending_revenue = 0.0
    delivery_fees = 0.0
    points_redeemed = 0
    total_garments = 0

    order_ids = [o.order_id for o in orders]

    pickup_orders_count = 0
    pickup_revenue = 0.0
    store_drop_orders_count = 0
    store_drop_revenue = 0.0

    payment_modes = {"UPI": 0, "CASH": 0, "PENDING": 0}
    payment_statuses = {"PAID": 0, "PENDING": 0}

    status_counts = {
        "PENDING_PICKUP": 0,
        "IN_SHOP": 0,
        "PROCESSING": 0,
        "READY": 0,
        "DELIVERED": 0,
        "CANCELLED": 0,
        "REJECTED": 0
    }

    customer_spend_map = {}
    valid_orders_count = 0
    cancelled_orders_count = 0
    valid_order_ids = []

    for o in orders:
        status_key = o.status.name if hasattr(o.status, "name") else str(o.status)
        status_counts[status_key] = status_counts.get(status_key, 0) + 1

        # CRITICAL: Exclude cancelled & rejected orders from revenue, unpaid section, channels & garments!
        if status_key in ["CANCELLED", "REJECTED"]:
            cancelled_orders_count += 1
            continue

        valid_orders_count += 1
        valid_order_ids.append(o.order_id)

        amt = o.total_amount if o.total_amount is not None else (o.estimated_amount or 0.0)
        fee = o.delivery_fee or 0.0
        pts = o.points_redeemed or 0
        effective_total = max(0.0, amt + fee - pts)

        total_revenue += effective_total
        delivery_fees += fee
        points_redeemed += pts
        total_garments += (o.item_count or 0)

        # Channel
        is_store_drop = False
        if hasattr(o, "order_type") and o.order_type:
            otype_str = o.order_type.name if hasattr(o.order_type, "name") else str(o.order_type)
            if otype_str == "STORE_DROP":
                is_store_drop = True

        if is_store_drop:
            store_drop_orders_count += 1
            store_drop_revenue += effective_total
        else:
            pickup_orders_count += 1
            pickup_revenue += effective_total

        # Payment status (Only active/completed orders count as PAID or PENDING unpaid receivables)
        p_status_key = o.payment_status.name if hasattr(o.payment_status, "name") else str(o.payment_status or "PENDING")
        if p_status_key == "PAID":
            paid_revenue += effective_total
            payment_statuses["PAID"] += 1
        else:
            pending_revenue += effective_total
            payment_statuses["PENDING"] += 1

        # Payment mode
        p_mode_key = o.payment_mode.name if (hasattr(o, "payment_mode") and o.payment_mode and hasattr(o.payment_mode, "name")) else (str(o.payment_mode) if o.payment_mode else None)
        if p_mode_key == "UPI":
            payment_modes["UPI"] += 1
        elif p_mode_key == "CASH":
            payment_modes["CASH"] += 1
        else:
            payment_modes["PENDING"] += 1

        # Customer aggregation
        if o.customer:
            cid = o.customer_id
            cname = o.customer.name or f"Customer #{cid}"
            cphone = o.customer.phone_number
            if cid not in customer_spend_map:
                customer_spend_map[cid] = {"id": cid, "name": cname, "phone": cphone, "orders": 0, "spend": 0.0}
            customer_spend_map[cid]["orders"] += 1
            customer_spend_map[cid]["spend"] += effective_total

    # Services & Garments breakdown (only for valid non-cancelled orders)
    services_counts = {}
    garment_counts = {}

    if valid_order_ids:
        items = db.query(OrderItem).filter(OrderItem.order_id.in_(valid_order_ids)).all()
        for it in items:
            s_name = (it.service_type or "Dry Clean").replace("_", " ").title()
            g_name = (it.garment_type or "Garment").title()
            qty = it.quantity or 1
            services_counts[s_name] = services_counts.get(s_name, 0) + qty
            garment_counts[g_name] = garment_counts.get(g_name, 0) + qty

    # Customer Demographics
    total_customers_db = db.query(Customer).count()
    repeat_customers = db.query(Customer).filter(Customer.order_count >= 2).count()
    languages_query = db.query(Customer.preferred_language, func.count(Customer.customer_id)).group_by(Customer.preferred_language).all()
    language_breakdown = {}
    for lang, count in languages_query:
        language_breakdown[lang or "ENGLISH"] = count

    # Top customers list sorted by spend
    top_customers = sorted(customer_spend_map.values(), key=lambda x: (x["spend"], x["orders"]), reverse=True)[:5]

    # Helper for filtering out cancelled orders from trend buckets
    def is_valid_order(ord_obj):
        st = ord_obj.status.name if hasattr(ord_obj.status, "name") else str(ord_obj.status)
        return st not in ["CANCELLED", "REJECTED"]

    # Timeline trends based on timeframe (only non-cancelled orders count)
    trends = []
    if timeframe == "daily":
        time_buckets = [
            ("09:00 - 11:00", 9, 11),
            ("11:00 - 13:00", 11, 13),
            ("13:00 - 15:00", 13, 15),
            ("15:00 - 17:00", 15, 17),
            ("17:00 - 19:00", 17, 19),
            ("19:00 - 21:00", 19, 21),
        ]
        for label, h_start, h_end in time_buckets:
            b_orders = [o for o in orders if o.created_at and h_start <= o.created_at.hour < h_end and is_valid_order(o)]
            b_rev = sum([
                max(0.0, (o.total_amount if o.total_amount is not None else (o.estimated_amount or 0.0)) + (o.delivery_fee or 0.0) - (o.points_redeemed or 0))
                for o in b_orders
            ])
            trends.append({"label": label, "orders": len(b_orders), "revenue": round(b_rev, 2)})

    elif timeframe == "weekly":
        for i in range(6, -1, -1):
            d = (current_time - timedelta(days=i))
            d_start = d.replace(hour=0, minute=0, second=0, microsecond=0)
            d_end = d.replace(hour=23, minute=59, second=59, microsecond=999999)
            d_orders = [o for o in orders if o.created_at and d_start <= o.created_at <= d_end and is_valid_order(o)]
            d_rev = sum([
                max(0.0, (o.total_amount if o.total_amount is not None else (o.estimated_amount or 0.0)) + (o.delivery_fee or 0.0) - (o.points_redeemed or 0))
                for o in d_orders
            ])
            trends.append({
                "label": d.strftime("%a (%d %b)"),
                "orders": len(d_orders),
                "revenue": round(d_rev, 2)
            })

    elif timeframe == "monthly":
        for i in range(3, -1, -1):
            w_start_days = (i + 1) * 7
            w_end_days = i * 7
            w_start = (current_time - timedelta(days=w_start_days)).replace(hour=0, minute=0, second=0, microsecond=0)
            w_end = (current_time - timedelta(days=w_end_days)).replace(hour=23, minute=59, second=59, microsecond=999999)
            w_orders = [o for o in orders if o.created_at and w_start <= o.created_at <= w_end and is_valid_order(o)]
            w_rev = sum([
                max(0.0, (o.total_amount if o.total_amount is not None else (o.estimated_amount or 0.0)) + (o.delivery_fee or 0.0) - (o.points_redeemed or 0))
                for o in w_orders
            ])
            lbl = f"Week {4 - i}" if i > 0 else "Current Week"
            trends.append({
                "label": f"{lbl} ({w_start.strftime('%d %b')} - {w_end.strftime('%d %b')})",
                "orders": len(w_orders),
                "revenue": round(w_rev, 2)
            })

    elif timeframe in ["quarterly", "annual", "all"]:
        num_months = 3 if timeframe == "quarterly" else (12 if timeframe == "annual" else 6)
        for i in range(num_months - 1, -1, -1):
            target_date = current_time - timedelta(days=i * 30)
            y, m = target_date.year, target_date.month
            m_orders = [o for o in orders if o.created_at and o.created_at.year == y and o.created_at.month == m and is_valid_order(o)]
            m_rev = sum([
                max(0.0, (o.total_amount if o.total_amount is not None else (o.estimated_amount or 0.0)) + (o.delivery_fee or 0.0) - (o.points_redeemed or 0))
                for o in m_orders
            ])
            trends.append({
                "label": target_date.strftime("%b %Y"),
                "orders": len(m_orders),
                "revenue": round(m_rev, 2)
            })

    avg_order_val = (total_revenue / valid_orders_count) if valid_orders_count > 0 else 0.0

    return {
        "timeframe": timeframe,
        "period_label": period_label,
        "kpis": {
            "total_revenue": round(total_revenue, 2),
            "paid_revenue": round(paid_revenue, 2),
            "pending_revenue": round(pending_revenue, 2),
            "total_orders": valid_orders_count,
            "cancelled_orders": cancelled_orders_count,
            "total_garments": total_garments,
            "avg_order_value": round(avg_order_val, 2),
            "delivery_fees_collected": round(delivery_fees, 2),
            "points_redeemed": points_redeemed
        },
        "channels": {
            "pickup": {
                "orders": pickup_orders_count,
                "revenue": round(pickup_revenue, 2),
                "share_pct": round((pickup_orders_count / valid_orders_count * 100), 1) if valid_orders_count > 0 else 0
            },
            "store_drop": {
                "orders": store_drop_orders_count,
                "revenue": round(store_drop_revenue, 2),
                "share_pct": round((store_drop_orders_count / valid_orders_count * 100), 1) if valid_orders_count > 0 else 0
            }
        },
        "payments": {
            "modes": payment_modes,
            "statuses": payment_statuses
        },
        "funnel": status_counts,
        "services": services_counts,
        "top_garments": sorted([{"name": k, "count": v} for k, v in garment_counts.items()], key=lambda x: x["count"], reverse=True)[:8],
        "customers": {
            "total_registered": total_customers_db,
            "repeat_customers": repeat_customers,
            "repeat_rate_pct": round((repeat_customers / total_customers_db * 100), 1) if total_customers_db > 0 else 0,
            "languages": language_breakdown,
            "top_customers": top_customers
        },
        "trends": trends
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

    if order.order_type.name == "PICKUP" and order.status.name == "PENDING_PICKUP" and new_status not in ["PENDING_PICKUP", "CANCELLED", "REJECTED"] and not order.runner_id:
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
    location = (order.customer.last_location_gps if order.customer and order.customer.last_location_gps else order.flat_address) or "No Location Provided"
    from app.services.crud import get_google_maps_url
    maps_link = get_google_maps_url(location) if location != "No Location Provided" else "No link available."
    if not maps_link:
        maps_link = "No link available."

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

class CreateOrderItemInput(BaseModel):
    garment_type: str
    service_type: str
    quantity: int = 1
    price: float = 0.0
    special_notes: Optional[str] = None

class CreateCounterOrderRequest(BaseModel):
    customer_id: Optional[int] = None
    new_customer_name: Optional[str] = None
    new_customer_phone: Optional[str] = None
    new_customer_address: Optional[str] = None
    
    # Optional aliases
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    
    order_type: str = "STORE_DROP"  # "STORE_DROP" (Store Walk-in) or "PICKUP" (Pickup & Delivery)
    service_category: Optional[str] = "Dry Clean"
    flat_address: Optional[str] = ""
    items: List[CreateOrderItemInput] = []
    
    total_amount: float = 0.0
    delivery_fee: float = 0.0
    points_redeemed: int = 0
    
    payment_status: str = "PENDING"  # "PENDING" or "PAID"
    payment_mode: Optional[str] = "CASH"  # "CASH" or "UPI"
    runner_id: Optional[int] = None
    special_instructions: Optional[str] = ""
    
    resume_bot: bool = True
    send_whatsapp_receipt: bool = True

@router.post("/counter")
def create_counter_order(req: CreateCounterOrderRequest, db: Session = Depends(get_db)):
    """
    Creates an in-store counter walk-in order or manual delivery order.
    Auto-prices garments, sends WhatsApp confirmation receipt, and resets bot state to IDLE.
    """
    from app.services.crud import _generate_next_order_id, create_customer
    from app.services.whatsapp_sender import send_order_receipt_whatsapp
    from app.core.graph import reset_customer_bot_state
    from app.core.ws_manager import broadcast_event_sync

    # 1. Resolve Customer
    customer = None
    resolved_phone = req.new_customer_phone or req.customer_phone
    resolved_name = req.new_customer_name or req.customer_name
    resolved_address = req.new_customer_address or req.flat_address or ""

    if req.customer_id:
        customer = db.query(Customer).filter_by(customer_id=req.customer_id).first()
        if not customer:
            raise HTTPException(status_code=404, detail="Selected customer not found")
        if req.flat_address and not customer.saved_address:
            customer.saved_address = req.flat_address
            db.commit()
    elif resolved_phone:
        from app.services.whatsapp_sender import format_whatsapp_number
        clean_phone = format_whatsapp_number(resolved_phone)
        if not clean_phone or len(clean_phone) < 12:
            raise HTTPException(status_code=400, detail="Invalid phone number for new customer")
        
        customer = db.query(Customer).filter(
            (Customer.phone_number == clean_phone) |
            (Customer.phone_number.like(f"%{clean_phone[-10:]}%"))
        ).first()
        if not customer:
            customer = create_customer(
                db,
                phone_number=clean_phone,
                name=resolved_name or "Walk-in Customer",
                saved_address=resolved_address
            )
        else:
            if customer.phone_number != clean_phone:
                customer.phone_number = clean_phone
            if resolved_name and (not customer.name or customer.name.startswith("Customer")):
                customer.name = resolved_name
            if resolved_address and not customer.saved_address:
                customer.saved_address = resolved_address
            db.commit()
    else:
        raise HTTPException(status_code=400, detail="Customer must be selected or phone number provided")

    # 2. Determine Order Types & Initial Status
    is_store_drop = (req.order_type == "STORE_DROP")
    order_type_enum = OrderType.STORE_DROP if is_store_drop else OrderType.PICKUP
    initial_status_enum = OrderStatus.IN_SHOP if is_store_drop else OrderStatus.PENDING_PICKUP
    payment_status_enum = PaymentStatus.PAID if req.payment_status == "PAID" else PaymentStatus.PENDING
    payment_mode_enum = None
    if req.payment_status == "PAID" and req.payment_mode:
        payment_mode_enum = PaymentMode.UPI if req.payment_mode.upper() == "UPI" else PaymentMode.CASH

    # 3. Generate sequential order ID
    order_id = _generate_next_order_id(db)

    # 4. Calculate item count & auto-calculate total_amount if not provided
    total_qty = sum(item.quantity for item in req.items) if req.items else 1
    items_subtotal = sum(item.quantity * item.price for item in req.items) if req.items else 0.0
    effective_subtotal = req.total_amount if req.total_amount > 0 else items_subtotal

    # 5. Insert Order
    db_order = Order(
        order_id=order_id,
        customer_id=customer.customer_id,
        order_type=order_type_enum,
        status=initial_status_enum,
        item_count=total_qty,
        total_amount=effective_subtotal,
        estimated_amount=effective_subtotal,
        delivery_fee=0.0 if is_store_drop else req.delivery_fee,
        points_redeemed=req.points_redeemed,
        payment_status=payment_status_enum,
        payment_mode=payment_mode_enum,
        disclaimer_accepted=True,
        runner_id=req.runner_id,
        service_category=req.service_category or "Dry Clean",
        flat_address=req.flat_address or customer.saved_address or "",
        special_instructions=req.special_instructions or "",
        created_at=now_ist(),
        picked_up_at=now_ist() if is_store_drop else None
    )
    db.add(db_order)
    customer.order_count = (customer.order_count or 0) + 1
    db.commit()
    db.refresh(db_order)

    # 6. Insert Order Items
    for it in req.items:
        db_item = OrderItem(
            order_id=order_id,
            garment_type=it.garment_type,
            service_type=it.service_type,
            quantity=it.quantity,
            special_notes=it.special_notes
        )
        db.add(db_item)
    db.commit()

    # 7. Deduct Points if redeemed
    if req.points_redeemed > 0:
        add_points_transaction(db, customer.customer_id, req.points_redeemed, "REDEEMED", order_id)

    # 8. Resume AI Bot & Reset State to IDLE
    if req.resume_bot:
        if customer.bot_paused:
            customer.bot_paused = False
            db.commit()
            try:
                broadcast_event_sync("CHAT_BOT_TOGGLED", {
                    "customer_id": customer.customer_id,
                    "bot_paused": False
                })
            except Exception:
                pass
        # Reset LangGraph conversational checkpoint to clean IDLE
        reset_customer_bot_state(customer.phone_number)

    # 9. Send WhatsApp Confirmation Receipt
    if req.send_whatsapp_receipt and customer.phone_number:
        try:
            items_payload = [
                {
                    "garment_type": it.garment_type,
                    "service_type": it.service_type,
                    "quantity": it.quantity,
                    "price": it.price
                }
                for it in req.items
            ]
            from app.services.whatsapp_sender import format_whatsapp_number
            target_phone = format_whatsapp_number(customer.phone_number)
            send_res = send_order_receipt_whatsapp(
                phone_number=target_phone,
                order_id=order_id,
                customer_name=customer.name,
                order_type=req.order_type,
                items=items_payload,
                total_amount=effective_subtotal,
                delivery_fee=0.0 if is_store_drop else req.delivery_fee,
                points_redeemed=req.points_redeemed,
                payment_status=req.payment_status
            )
            logger.info(f"WhatsApp order receipt send result for #{order_id} to {target_phone}: {send_res}")
        except Exception as e:
            logger.error(f"Failed to send WhatsApp confirmation receipt for order #{order_id}: {e}")

    # 10. Broadcast real-time WebSocket event
    try:
        broadcast_event_sync("ORDER_CREATED", {
            "order_id": db_order.order_id,
            "customer_id": customer.customer_id,
            "item_count": total_qty,
            "service_category": req.service_category
        })
    except Exception as e:
        logger.warning(f"Failed to broadcast ORDER_CREATED event for order #{order_id}: {e}")

    db.refresh(db_order)
    return serialize_order(db_order)
