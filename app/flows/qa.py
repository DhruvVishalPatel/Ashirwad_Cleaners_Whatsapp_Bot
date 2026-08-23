from typing import Dict, Any
from app.services.whatsapp_sender import send_text_message, send_interactive_buttons
from app.core.translations import t
from app.core.llm_router import generate_estimate

def greeting_node(state: dict) -> Dict[str, Any]:
    """
    Welcomes user and presents entry point choices.
    """
    lang = state["language"]
    buttons = [
        {"id": "btn_intent_pricing", "title": t("GREETING_BUTTON_PRICING", lang)},
        {"id": "btn_intent_status", "title": t("GREETING_BUTTON_STATUS", lang)},
        {"id": "btn_intent_pickup", "title": t("GREETING_BUTTON_PICKUP", lang)}
    ]
    send_interactive_buttons(state["phone_number"], t("WELCOME_MSG", lang), buttons)
    
    return {
        "current_flow": "IDLE",
        "current_state": "",
        "response_sent": True
    }

def change_language_node(state: dict) -> Dict[str, Any]:
    """
    Prompts the user to select their preferred language.
    """
    buttons = [
        {"id": "btn_lang_english", "title": "English"},
        {"id": "btn_lang_hinglish", "title": "Hindi (Hinglish)"},
        {"id": "btn_lang_gujlish", "title": "Gujarati (Gujlish)"}
    ]
    send_interactive_buttons(state["phone_number"], t("ASK_LANGUAGE", "ENGLISH"), buttons)
    
    return {
        "current_flow": "IDLE",
        "current_state": "AWAITING_LANGUAGE_SELECTION",
        "response_sent": True
    }

def qa_node(state: dict) -> Dict[str, Any]:
    """
    Resolves conversational queries / interruptions. Resumes flow if paused.
    """
    lang = state["language"]
    text = state["text_input"]
    
    estimate_data = generate_estimate(text, lang)
    reply = estimate_data.get("reply", "I'm not sure how to answer that.")
    
    send_text_message(state["phone_number"], reply)
    
    if state.get("last_active_state"):
        resumption_msg = t("ESTIMATE_QUESTION_SUFFIX", lang)
        send_text_message(state["phone_number"], resumption_msg)
        return {
            "current_flow": "PICKUP",
            "current_state": state["last_active_state"],
            "last_active_state": "",
            "response_sent": True
        }
        
    return {
        "current_flow": "IDLE",
        "current_state": "",
        "response_sent": True
    }
