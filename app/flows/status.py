from app.services.whatsapp_sender import send_text_message
from app.services.crud import get_active_orders

def handle_status_flow(phone_number: str, text: str, db, customer_id: int):
    orders = get_active_orders(db, customer_id)
    
    if not orders:
        send_text_message(phone_number, "You don't have any active orders right now. Would you like to schedule a pickup? Just say 'Pickup'!")
        return
        
    if len(orders) == 1:
        order = orders[0]
        send_text_message(phone_number, f"Order #{order.order_id} status: {order.status.name}. Estimated completion: Tomorrow.")
    else:
        # If multiple, in a full app we'd send a WhatsApp List Message.
        # For simplicity in MVP, we just list them out.
        msg = "You have multiple active orders:\n"
        for o in orders:
            msg += f"- #{o.order_id}: {o.status.name}\n"
        send_text_message(phone_number, msg)
