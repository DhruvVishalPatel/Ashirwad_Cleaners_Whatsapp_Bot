import os
import requests
import json

WA_PHONE_NUMBER_ID = os.environ.get("WA_PHONE_NUMBER_ID")
WA_ACCESS_TOKEN = os.environ.get("WA_ACCESS_TOKEN")
GRAPH_API_VERSION = "v19.0"

def send_text_message(to_number: str, text: str):
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

def send_interactive_buttons(to_number: str, body_text: str, buttons: list):
    """buttons should be a list of dicts: [{'id': 'btn_1', 'title': 'Yes'}, ...] max 3"""
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
