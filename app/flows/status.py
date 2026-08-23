from typing import Dict, Any
from app.core.database import SessionLocal
from app.services.whatsapp_sender import send_text_message
from app.core.translations import t
from app.services.crud import get_active_orders

STATUS_HUMAN_MAP = {
    "PENDING_PICKUP": "Pending Pickup",
    "PICKED_UP": "Picked Up",
    "IN_SHOP": "Received at Shop",
    "PROCESSING": "In Cleaning & Processing",
    "READY": "Ready for Delivery",
    "OUT_FOR_DELIVERY": "Out for Delivery",
    "DELIVERED": "Delivered",
    "CANCELLED": "Cancelled",
    "REJECTED": "Rejected"
}

def format_status_display(status_obj) -> str:
    raw_str = status_obj.name if hasattr(status_obj, "name") else str(status_obj)
    return STATUS_HUMAN_MAP.get(raw_str, raw_str.replace("_", " ").title())

def status_node(state: dict) -> Dict[str, Any]:
    """
    Shows status of user's active orders.
    """
    lang = state["language"]
    
    with SessionLocal() as db:
        orders = get_active_orders(db, state["customer_id"])
    
    if not orders:
        send_text_message(state["phone_number"], t("STATUS_NO_ORDERS", lang))
    elif len(orders) == 1:
        order = orders[0]
        status_str = format_status_display(order.status)
        send_text_message(state["phone_number"], t("STATUS_SINGLE_ORDER", lang, order_id=order.order_id, status_name=status_str))
    else:
        msg = t("STATUS_MULTIPLE_ORDERS", lang)
        for o in orders:
            status_str = format_status_display(o.status)
            msg += f"- #{o.order_id}: {status_str}\n"
        send_text_message(state["phone_number"], msg)
        
    return {
        "current_flow": "IDLE",
        "current_state": "",
        "response_sent": True
    }
