import os
import requests
import json
from app.core.logger import logger

WA_PHONE_NUMBER_ID = os.environ.get("WA_PHONE_NUMBER_ID")
WA_ACCESS_TOKEN = os.environ.get("WA_ACCESS_TOKEN")
GRAPH_API_VERSION = "v19.0"

def format_whatsapp_number(phone: str) -> str:
    """
    Normalizes any input phone number into Meta WhatsApp Cloud API format (E.164 without '+').
    For Indian numbers: exactly 12 digits starting with '91' (e.g. 919876543210).
    Handles 10-digit inputs, leading '0', '+91', spaces, and dashes.
    """
    if not phone:
        return ""
    digits = "".join(filter(str.isdigit, str(phone)))
    if len(digits) == 10:
        return f"91{digits}"
    if len(digits) == 11 and digits.startswith("0"):
        return f"91{digits[1:]}"
    if len(digits) == 12 and digits.startswith("91"):
        return digits
    if len(digits) > 10:
        return f"91{digits[-10:]}"
    return digits

def _auto_log_outbound(to_number: str, content: str, sender_type: str = "BOT", message_type: str = "text", media_url: str = None):
    try:
        from app.core.database import SessionLocal
        from app.services.crud import get_customer, log_chat_message
        norm_number = format_whatsapp_number(to_number)
        with SessionLocal() as db:
            customer = get_customer(db, norm_number)
            if customer:
                log_chat_message(
                    db,
                    customer_id=customer.customer_id,
                    phone_number=norm_number,
                    sender_type=sender_type,
                    content=content,
                    message_type=message_type,
                    media_url=media_url
                )
    except Exception:
        pass

def send_text_message(to_number: str, text: str, sender_type: str = "BOT"):
    to_number = format_whatsapp_number(to_number)
    _auto_log_outbound(to_number, text, sender_type=sender_type, message_type="text")
    if not WA_ACCESS_TOKEN:
        print(f"MOCK WA SEND [TEXT] to {to_number}: {text}")
        return {"status": "mocked"}
        
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{WA_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WA_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "text",
        "text": {"preview_url": False, "body": text}
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code >= 400:
            logger.error(f"WhatsApp send_text error [{response.status_code}]: {response.text}")
        return response.json()
    except Exception as e:
        logger.error(f"WhatsApp send_text request failed for {to_number}: {e}")
        return {"error": str(e)}

def send_interactive_buttons(to_number: str, body_text: str, buttons: list, sender_type: str = "BOT"):
    to_number = format_whatsapp_number(to_number)
    btn_titles = ", ".join([f"[{b.get('title')}]" for b in buttons])
    full_content = f"{body_text}\n{btn_titles}" if btn_titles else body_text
    _auto_log_outbound(to_number, full_content, sender_type=sender_type, message_type="interactive")

    if not WA_ACCESS_TOKEN:
        print(f"MOCK WA SEND [BUTTONS] to {to_number}: {body_text} | Buttons: {buttons}")
        return {"status": "mocked"}
        
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{WA_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WA_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    interactive_buttons = []
    for btn in buttons:
        interactive_buttons.append({
            "type": "reply",
            "reply": {
                "id": btn["id"],
                "title": btn["title"]
            }
        })
        
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body_text},
            "action": {"buttons": interactive_buttons}
        }
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code >= 400:
            logger.error(f"WhatsApp send_interactive_buttons error [{response.status_code}]: {response.text}")
        return response.json()
    except Exception as e:
        logger.error(f"WhatsApp send_interactive_buttons request failed for {to_number}: {e}")
        return {"error": str(e)}

def send_image_message(to_number: str, image_url: str, caption: str = None, sender_type: str = "BOT"):
    to_number = format_whatsapp_number(to_number)
    content = caption or "[Image Message]"
    _auto_log_outbound(to_number, content, sender_type=sender_type, message_type="image", media_url=image_url)

    if not WA_ACCESS_TOKEN:
        print(f"MOCK WA SEND [IMAGE] to {to_number}: {image_url} | Caption: {caption}")
        return {"status": "mocked"}
        
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{WA_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WA_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "image",
        "image": {
            "link": image_url
        }
    }
    if caption:
        payload["image"]["caption"] = caption
        
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code >= 400:
            logger.error(f"WhatsApp send_image error [{response.status_code}]: {response.text}")
        return response.json()
    except Exception as e:
        logger.error(f"WhatsApp send_image request failed for {to_number}: {e}")
        return {"error": str(e)}

def send_order_receipt_whatsapp(
    phone_number: str,
    order_id: str,
    customer_name: str,
    order_type: str,
    items: list,
    total_amount: float,
    delivery_fee: float,
    points_redeemed: int,
    payment_status: str
):
    """
    Sends an itemized official WhatsApp order confirmation receipt to the customer.
    """
    type_display = "🏬 Walk-in Store Drop" if order_type == "STORE_DROP" else "🚚 Home Pickup & Delivery"
    pickup_note = "Self-Pickup from Shop" if order_type == "STORE_DROP" else "Home Delivery"
    payment_display = "PAID (Completed)" if payment_status == "PAID" else "UNPAID (Pending)"
    
    items_breakdown = ""
    for it in items:
        qty = it.get("quantity", 1)
        g_name = it.get("garment_type", "Garment")
        s_type = it.get("service_type", "Dry Clean")
        u_price = it.get("price") or it.get("unit_price") or 0.0
        line_tot = float(u_price) * int(qty)
        items_breakdown += f"• {qty}x {g_name} ({s_type}) - ₹{line_tot:.0f}\n"

    final_total = max(0.0, float(total_amount) + float(delivery_fee) - float(points_redeemed))

    receipt_text = (
        f"🧺 *ASHIRWAD CLEANERS - ORDER CONFIRMATION*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Order ID: *#{order_id}*\n"
        f"Customer: *{customer_name or 'Valued Customer'}*\n"
        f"Order Type: *{type_display}*\n\n"
        f"📦 *Garments Breakdown:*\n"
        f"{items_breakdown.strip()}\n\n"
        f"Subtotal: *₹{total_amount:.0f}*\n"
        f"Delivery Fee: *₹{delivery_fee:.0f} ({pickup_note})*\n"
        f"Loyalty Discount: *-₹{points_redeemed}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Total Payable: *₹{final_total:.0f}*\n"
        f"Payment Status: *{payment_display}*\n\n"
        f"📍 *Shop Address:* G-1, Raj Nagar Complex, Narayan Nagar Road, Paldi, Ahmedabad.\n"
        f"📞 *Shop Manager:* Faizan (+91 84698 42889)\n\n"
        f"✨ We will notify you on WhatsApp as soon as your garments are ready!"
    )
    return send_text_message(phone_number, receipt_text, sender_type="BOT")


