import os
import json
from app.services.whatsapp_sender import send_text_message, send_interactive_buttons
from app.core.state_machine import set_session_state, clear_session

def load_price_list():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    file_path = os.path.join(base_dir, "price_list.json")
    with open(file_path, "r") as f:
        return json.load(f)

def format_category_pricing(category_key: str) -> str:
    data = load_price_list()
    services = data.get("services", {})
    category = services.get(category_key)
    
    if not category:
        return "Pricing not found."
        
    title = category_key.replace("_", " ").title()
    desc = category.get("description", "")
    
    text = f"*{title} Prices* 👔\n_{desc}_\n\n"
    
    rule = category.get("business_rule")
    if rule:
        text += f"⚠️ *Note*: {rule.get('validation_error_message')}\n\n"
        
    for item in category.get("items", []):
        name = item.get("item_name")
        price = item.get("base_price")
        note = item.get("note")
        
        line = f"• {name}: ₹{price}"
        if note:
            line += f" ({note})"
        text += line + "\n"
        
    text += "\nTo schedule a pickup, just reply with 'Pickup'!"
    return text

def handle_pricing_flow(phone_number: str, text: str = "", session_data: dict = None):
    current_state = session_data.get("state") if session_data else None
    
    if not current_state or current_state == "INTENT_PRICING":
        buttons = [
            {"id": "btn_price_dry_clean", "title": "Dry Clean"},
            {"id": "btn_price_washing", "title": "Washing"},
            {"id": "btn_price_steam_press", "title": "Steam Press"}
        ]
        send_interactive_buttons(
            phone_number, 
            "We have three main service categories! Which pricing list would you like to view?", 
            buttons
        )
        set_session_state(phone_number, "PRICING_AWAITING_SELECTION", {})
        return
        
    if current_state == "PRICING_AWAITING_SELECTION":
        mapping = {
            "btn_price_dry_clean": "dry_clean",
            "btn_price_washing": "washing",
            "btn_price_steam_press": "steam_press"
        }
        
        category_key = mapping.get(text)
        
        if category_key:
            catalog_text = format_category_pricing(category_key)
            send_text_message(phone_number, catalog_text)
            clear_session(phone_number)
        else:
            send_text_message(phone_number, "Please tap one of the category buttons above.")
        return
