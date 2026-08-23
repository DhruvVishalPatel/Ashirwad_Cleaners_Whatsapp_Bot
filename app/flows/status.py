from typing import Dict, Any
from app.core.database import SessionLocal
from app.services.whatsapp_sender import send_text_message
from app.core.translations import t
from app.services.crud import get_active_orders

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
        send_text_message(state["phone_number"], t("STATUS_SINGLE_ORDER", lang, order_id=order.order_id, status_name=order.status.name))
    else:
        msg = t("STATUS_MULTIPLE_ORDERS", lang)
        for o in orders:
            msg += f"- #{o.order_id}: {o.status.name}\n"
        send_text_message(state["phone_number"], msg)
        
    return {
        "current_flow": "IDLE",
        "current_state": "",
        "response_sent": True
    }
