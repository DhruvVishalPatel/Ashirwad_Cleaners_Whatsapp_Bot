import os
from typing import Dict, Any
from app.services.whatsapp_sender import send_image_message
from app.core.translations import t

def pricing_node(state: dict) -> Dict[str, Any]:
    """
    Directly sends the static price list image to the customer.
    """
    lang = state["language"]
    
    # Construct base URL for static image serving
    base_url = os.environ.get("BASE_URL", "https://api.ashirwadcleaners.in")
    image_url = f"{base_url}/static/price_list.png"
    
    send_image_message(state["phone_number"], image_url, t("PRICING_IMAGE_CAPTION", lang))
    
    return {
        "current_flow": "IDLE",
        "current_state": "",
        "response_sent": True
    }
