import os
from typing import Dict, Any
from app.services.whatsapp_sender import send_image_message, send_text_message
from app.core.translations import t

def pricing_node(state: dict) -> Dict[str, Any]:
    """
    Directly sends the static price list image to the customer.
    Resumes active flow if interrupted.
    """
    lang = state["language"]
    
    # Construct base URL for static image serving (fallback to live domain if ngrok/empty)
    base_url = (os.environ.get("BASE_URL") or "https://api.ashirwadcleaners.in").strip().rstrip("/")
    if "ngrok" in base_url or not base_url.startswith("http"):
        base_url = "https://api.ashirwadcleaners.in"
    image_url = f"{base_url}/static/price_list.png"
    
    send_image_message(state["phone_number"], image_url, t("PRICING_IMAGE_CAPTION", lang))
    
    last_state = state.get("last_active_state")
    if last_state:
        if last_state == "PICKUP_AWAITING_NAME":
            send_text_message(state["phone_number"], t("ASK_NAME", lang))
        else:
            send_text_message(state["phone_number"], t("ESTIMATE_QUESTION_SUFFIX", lang).lstrip())
        return {
            "current_flow": "PICKUP",
            "current_state": last_state,
            "last_active_state": "",
            "response_sent": True
        }

    return {
        "current_flow": "IDLE",
        "current_state": "",
        "response_sent": True
    }
