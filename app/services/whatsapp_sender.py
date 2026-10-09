import os
import requests
import json

WA_PHONE_NUMBER_ID = os.environ.get("WA_PHONE_NUMBER_ID")
WA_ACCESS_TOKEN = os.environ.get("WA_ACCESS_TOKEN")
GRAPH_API_VERSION = "v19.0"

def _auto_log_outbound(to_number: str, content: str, sender_type: str = "BOT", message_type: str = "text", media_url: str = None):
    try:
        from app.core.database import SessionLocal
        from app.services.crud import get_customer, log_chat_message
        with SessionLocal() as db:
            customer = get_customer(db, to_number)
            if customer:
                log_chat_message(
                    db,
                    customer_id=customer.customer_id,
                    phone_number=to_number,
                    sender_type=sender_type,
                    content=content,
                    message_type=message_type,
                    media_url=media_url
                )
    except Exception:
        pass

def send_text_message(to_number: str, text: str, sender_type: str = "BOT"):
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
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

def send_interactive_buttons(to_number: str, body_text: str, buttons: list, sender_type: str = "BOT"):
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
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

def send_image_message(to_number: str, image_url: str, caption: str = None, sender_type: str = "BOT"):
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
        
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

