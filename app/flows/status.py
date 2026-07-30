from app.services.whatsapp_sender import send_text_message
from app.services.crud import get_active_orders
from app.core.translations import t
from app.models.schemas import Customer

def handle_status_flow(phone_number: str, text: str, db, customer_id: int):
    orders = get_active_orders(db, customer_id)
    
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    lang = customer.preferred_language if customer else "ENGLISH"
    
    if not orders:
        send_text_message(phone_number, t("STATUS_NO_ORDERS", lang))
        return
        
    if len(orders) == 1:
        order = orders[0]
        send_text_message(phone_number, t("STATUS_SINGLE_ORDER", lang, order_id=order.order_id, status_name=order.status.name))
    else:
        # If multiple, in a full app we'd send a WhatsApp List Message.
        # For simplicity in MVP, we just list them out.
        msg = t("STATUS_MULTIPLE_ORDERS", lang)
        for o in orders:
            msg += f"- #{o.order_id}: {o.status.name}\n"
        send_text_message(phone_number, msg)
