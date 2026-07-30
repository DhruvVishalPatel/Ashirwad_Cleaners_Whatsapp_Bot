import os
import json
from app.services.whatsapp_sender import send_text_message, send_interactive_buttons
from app.core.state_machine import set_session_state, clear_session
from app.core.translations import t
from app.core.database import SessionLocal
from app.models.schemas import Customer

def load_price_list():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    file_path = os.path.join(base_dir, "price_list.json")
    with open(file_path, "r") as f:
        return json.load(f)

def format_category_pricing(category_key: str, lang: str = "ENGLISH") -> str:
    data = load_price_list()
    services = data.get("services", {})
    category = services.get(category_key)
    
    if not category:
        return "Pricing not found."
        
    title = t(f"PRICING_TITLE_{category_key}", lang)
    desc = t(f"PRICING_DESC_{category_key}", lang)
    
    text = f"*{title}* 👔\n_{desc}_\n\n"
    
    rule = category.get("business_rule")
    if rule:
        note_msg = rule.get('validation_error_message')
        if lang == "HINGLISH":
            if "minimum" in note_msg.lower():
                note_msg = "Kam se kam 5 items hone chahiye."
        elif lang == "GUJLISH":
            if "minimum" in note_msg.lower():
                note_msg = "Ochha ma ochha 5 items joiye."
        text += f"⚠️ *Note*: {note_msg}\n\n"
        
    for item in category.get("items", []):
        name = item.get("item_name")
        price = item.get("base_price")
        note = item.get("note")
        
        line = f"• {name}: ₹{price}"
        if note:
            line += f" ({note})"
        text += line + "\n"
        
    text += t("PRICING_CATALOG_FOOTER", lang)
    return text

def handle_pricing_flow(phone_number: str, text: str = "", session_data: dict = None):
    current_state = session_data.get("state") if session_data else None
    
    # Load customer language preference
    db = SessionLocal()
    customer = db.query(Customer).filter(Customer.phone_number == phone_number).first()
    lang = customer.preferred_language if customer else "ENGLISH"
    db.close()
    
    if not current_state or current_state == "INTENT_PRICING":
        dry_clean_title = "Dry Clean"
        washing_title = "Washing" if lang == "ENGLISH" else ("Washing / Dhona" if lang == "HINGLISH" else "Washing / Dhova")
        steam_press_title = "Steam Press" if lang == "ENGLISH" else ("Steam Press / Istree" if lang == "HINGLISH" else "Steam Press / Istree")
        buttons = [
            {"id": "btn_price_dry_clean", "title": dry_clean_title},
            {"id": "btn_price_washing", "title": washing_title},
            {"id": "btn_price_steam_press", "title": steam_press_title}
        ]
        send_interactive_buttons(
            phone_number, 
            t("PRICING_SELECTION_MSG", lang), 
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
            catalog_text = format_category_pricing(category_key, lang)
            send_text_message(phone_number, catalog_text)
            clear_session(phone_number)
        else:
            send_text_message(phone_number, t("PRICING_AWAIT_SELECTION_ERROR", lang))
        return
