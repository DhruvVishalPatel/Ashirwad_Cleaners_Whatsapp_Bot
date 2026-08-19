import os
import json
import re
import sqlite3
from typing import TypedDict, List, Dict, Any, Literal
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from app.core.database import SessionLocal
from app.models.schemas import Customer, Order, OrderStatus
from app.services.whatsapp_sender import send_text_message, send_interactive_buttons, send_image_message
from app.core.translations import t
from app.core.llm_router import classify_intent, generate_estimate
from app.core.logger import logger
from app.services.crud import (
    create_order,
    update_customer_location,
    update_customer_name,
    get_customer_saved_address,
    update_customer_saved_address,
    get_monthly_order_count,
    get_available_points,
    get_active_orders
)

# ----------------- UTILITY HELPERS -----------------

def match_button_synonym(text: str, state: str) -> str:
    clean_text = text.strip().lower()
    
    # If the user clicked the button directly
    if clean_text in ["btn_redeem_yes", "btn_redeem_no", "btn_addr_yes", "btn_addr_new"]:
        return text.strip()
        
    if state == "PICKUP_AWAITING_POINTS_REDEEM":
        yes_syns = ["yes", "y", "yeah", "ok", "okay", "sure", "redeem", "haan", "ha", "theek hai", "chalega", "use karo", "saras", "vapro", "please use"]
        no_syns = ["no", "n", "nope", "save", "later", "save for later", "nahi", "na", "baad mein", "pachhi", "bachavo", "keep", "don't redeem"]
        if clean_text in yes_syns:
            return "btn_redeem_yes"
        if clean_text in no_syns:
            return "btn_redeem_no"
            
    elif state == "PICKUP_AWAITING_ADDRESS_BUTTON":
        yes_syns = ["yes", "y", "yeah", "ok", "okay", "sure", "use saved", "saved", "saved address", "same", "same address", "haan", "ha", "theek hai", "chalega", "use karo", "saras", "chalsho", "vapro", "use this"]
        new_syns = ["new", "new address", "change", "change address", "different", "different address", "naya", "naya address", "badlo", "change karo", "navu", "navu address", "other", "another"]
        if clean_text in yes_syns:
            return "btn_addr_yes"
        if clean_text in new_syns:
            return "btn_addr_new"
            
    return text

def extract_coords_from_url(url: str):
    match = re.search(r'(?:q|query|ll)=([+-]?\d+\.\d+),([+-]?\d+\.\d+)', url)
    if match:
        return float(match.group(1)), float(match.group(2))
    return None

def is_in_paldi_coordinate(lat: float, lon: float) -> bool:
    return (23.000 <= lat <= 23.028) and (72.550 <= lon <= 72.580)

def is_in_paldi_text(address: str) -> bool:
    return "paldi" in address.lower()

# ----------------- STATE SCHEMA -----------------

class BotState(TypedDict):
    phone_number: str
    customer_id: int
    language: str              # "ENGLISH", "HINGLISH", "GUJLISH"
    current_flow: str          # "IDLE", "PICKUP", "PRICING", "STATUS", "QA"
    current_state: str         # Sub-state in flows
    last_active_state: str     # Backtracking / Resume location
    
    # User Input Text
    text_input: str
    
    # Response to send
    response_sent: bool
    
    # Pickup Flow Variables
    customer_name: str
    garments_list: List[Dict[str, Any]]
    item_count: int
    base_estimate: float
    delivery_fee: float
    delivery_str: str
    points_redeemed: int
    saved_address: str
    promo_msg: str
    max_redeemable: int
    final_estimate: float
    pending_items_input: str
    direct_order_prefix: str

# ----------------- GRAPH NODES -----------------

def classifier_node(state: BotState) -> Dict[str, Any]:
    """
    Decides the intent, language, and potential backtracking requests.
    """
    text = state.get("text_input", "").strip()
    clean_text = text.lower()
    
    logger.info(f"[ClassifierNode] Entry. Current Flow: {state.get('current_flow')}, State: {state.get('current_state')}, Input: '{text}'")
    
    # 2. Check for explicit Language Selection Buttons
    if text.startswith("btn_lang_"):
        lang_map = {
            "btn_lang_english": "ENGLISH",
            "btn_lang_hinglish": "HINGLISH",
            "btn_lang_gujlish": "GUJLISH"
        }
        selected_lang = lang_map.get(text, "ENGLISH")
        
        # Persist preferred language choice in Database
        db = SessionLocal()
        customer = db.query(Customer).filter(Customer.customer_id == state["customer_id"]).first()
        if customer:
            customer.preferred_language = selected_lang
            db.commit()
        db.close()
        
        logger.info(f"[ClassifierNode] Language selected: {selected_lang}. Routing to GREETING flow.")
        return {
            "current_flow": "GREETING",
            "current_state": "",
            "last_active_state": "",
            "language": selected_lang,
            "response_sent": False
        }

    # 3. Check Global Reset Keywords
    reset_keywords = ["cancel", "restart", "start over", "reset", "radd", "cancel karo", "shuru se", "radd karo", "chodi do", "fari shuru karo"]
    if clean_text in reset_keywords:
        send_text_message(state["phone_number"], t("SESSION_CANCELLED", state["language"]))
        return {
            "current_flow": "IDLE",
            "current_state": "",
            "last_active_state": "",
            "response_sent": True
        }

    # 4. Check if Language is unspecified
    if not state.get("language") or state.get("language") not in ["ENGLISH", "HINGLISH", "GUJLISH"]:
        logger.info("[ClassifierNode] Unspecified language. Redirecting to CHANGE_LANGUAGE flow.")
        return {
            "current_flow": "CHANGE_LANGUAGE",
            "current_state": "",
            "last_active_state": "",
            "response_sent": False
        }
        
    # 5. Check if in active flow
    if state["current_flow"] != "IDLE":
        # Check if they clicked a button directly
        if text.startswith("btn_"):
            return {"response_sent": False}
            
        # Check if they typed a button synonym
        if state["current_state"] in ["PICKUP_AWAITING_POINTS_REDEEM", "PICKUP_AWAITING_ADDRESS_BUTTON"]:
            syn = match_button_synonym(text, state["current_state"])
            if syn in ["btn_redeem_yes", "btn_redeem_no", "btn_addr_yes", "btn_addr_new"]:
                return {"response_sent": False}
                
        # If it is NOT a button/synonym, check if they are asking a Q&A question or backtracking
        intent, detected_lang = classify_intent(text)
        
        # If user sends a greeting message, break out of the active flow and return to the main menu
        if intent == "INTENT_GREETING":
            logger.info(f"[ClassifierNode] Greeting received during active flow '{state['current_flow']}'. Resetting state and returning to main menu.")
            return {
                "current_flow": "GREETING",
                "current_state": "",
                "last_active_state": "",
                "garments_list": [],
                "item_count": 0,
                "points_redeemed": 0,
                "saved_address": "",
                "pending_items_input": "",
                "direct_order_prefix": "",
                "response_sent": False
            }
            
        # Check Backtracking Modifiers
        if state["current_flow"] == "PICKUP":
            backtrack_items = ["change items", "change clothes", "items badlo", "kapde badlo", "kapda badlo", "incorrect items", "wrong items"]
            backtrack_address = ["change address", "address badlo", "wrong address", "incorrect address", "naya address", "new address"]
            backtrack_name = ["change name", "naam badlo", "wrong name", "incorrect name"]
            
            if any(kw in clean_text for kw in backtrack_items):
                send_text_message(state["phone_number"], t("WELCOME_BACK", detected_lang, name=state.get("customer_name", "there")))
                return {
                    "language": detected_lang,
                    "current_state": "PICKUP_AWAITING_ITEMS",
                    "garments_list": [],
                    "item_count": 0,
                    "response_sent": True
                }
            elif any(kw in clean_text for kw in backtrack_address):
                send_text_message(state["phone_number"], t("ADDRESS_INPUT_NEW_REQUEST", detected_lang))
                return {
                    "language": detected_lang,
                    "current_state": "PICKUP_AWAITING_CONFIRMATION_ADDRESS",
                    "saved_address": "",
                    "response_sent": True
                }
            elif any(kw in clean_text for kw in backtrack_name):
                send_text_message(state["phone_number"], t("ASK_NAME", detected_lang))
                return {
                    "language": detected_lang,
                    "current_state": "PICKUP_AWAITING_NAME",
                    "customer_name": "",
                    "response_sent": True
                }
                
        # Check if change language request
        if intent == "INTENT_CHANGE_LANGUAGE":
            logger.info(f"[ClassifierNode] Change language requested during active flow '{state['current_flow']}'. Resetting state.")
            return {
                "current_flow": "CHANGE_LANGUAGE",
                "current_state": "",
                "last_active_state": "",
                "garments_list": [],
                "item_count": 0,
                "points_redeemed": 0,
                "saved_address": "",
                "pending_items_input": "",
                "direct_order_prefix": "",
                "response_sent": False
            }

        # Check if Q&A interrupt
        if intent in ["INTENT_QA", "INTENT_PRICING"]:
            return {
                "language": detected_lang,
                "current_flow": "QA",
                "last_active_state": state["current_state"],
                "response_sent": False
            }
            
        # Default: Let active flow process the text
        return {"response_sent": False}
        
    # 3. Route new intents
    # Button triggers bypass LLM
    if text == "btn_intent_pickup":
        intent, detected_lang = "INTENT_PICKUP", state["language"]
    elif text == "btn_intent_status":
        intent, detected_lang = "INTENT_STATUS", state["language"]
    elif text == "btn_intent_pricing":
        intent, detected_lang = "INTENT_PRICING", state["language"]
    else:
        intent, detected_lang = classify_intent(text)
        
    # Save detected language to customer record in database (only if it is not empty)
    if detected_lang:
        db = SessionLocal()
        customer = db.query(Customer).filter(Customer.customer_id == state["customer_id"]).first()
        if customer:
            customer.preferred_language = detected_lang
            db.commit()
        db.close()
    
    flow_mapping = {
        "INTENT_PICKUP": "PICKUP",
        "INTENT_STATUS": "STATUS",
        "INTENT_PRICING": "PRICING",
        "INTENT_GREETING": "GREETING",
        "INTENT_QA": "QA",
        "INTENT_CHANGE_LANGUAGE": "CHANGE_LANGUAGE"
    }
    
    next_flow = flow_mapping.get(intent, "QA")
    logger.info(f"[ClassifierNode] Output. Routed to Flow: {next_flow}, Language: {detected_lang}")
    return {
        "current_flow": next_flow,
        "language": detected_lang,
        "response_sent": False
    }

def greeting_node(state: BotState) -> Dict[str, Any]:
    """
    Welcomes user and presents the entry point choices.
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

def pickup_name_node(state: BotState) -> Dict[str, Any]:
    """
    Asks the customer for their name if not already cached.
    Supports directly parsing garments from the initial message.
    """
    lang = state["language"]
    input_text = state["text_input"].strip()
    clean_input = input_text.lower()
    is_direct_order = not (clean_input in ["pickup", "btn_intent_pickup", "order", "book", "laundry", "dry clean", "steam press"])
    
    if state.get("current_state") == "PICKUP_AWAITING_NAME":
        # Process the name input
        name = input_text
        db = SessionLocal()
        update_customer_name(db, state["customer_id"], name)
        db.close()
        
        # If there's a pending garments list from the previous turn, process it immediately
        pending_items = state.get("pending_items_input")
        if pending_items:
            return {
                "customer_name": name,
                "text_input": pending_items,  # Override input for the next node (pickup_items_node)
                "pending_items_input": "",
                "direct_order_prefix": t("NEW_CUSTOMER_PREFIX", lang, name=name),
                "current_state": "PICKUP_AWAITING_ITEMS",
                "response_sent": False  # Execute pickup_items_node immediately in the same turn
            }
            
        send_text_message(state["phone_number"], t("WELCOME_BACK", lang, name=name))
        return {
            "customer_name": name,
            "current_state": "PICKUP_AWAITING_ITEMS",
            "response_sent": True
        }
        
    # Check database cache
    db = SessionLocal()
    customer = db.query(Customer).filter(Customer.customer_id == state["customer_id"]).first()
    cached_name = customer.name if customer else None
    db.close()
    
    if cached_name:
        if is_direct_order:
            return {
                "customer_name": cached_name,
                "direct_order_prefix": t("WELCOME_BACK_PREFIX", lang, name=cached_name),
                "current_state": "PICKUP_AWAITING_ITEMS",
                "response_sent": False  # Execute pickup_items_node immediately in the same turn
            }
        else:
            send_text_message(state["phone_number"], t("WELCOME_BACK", lang, name=cached_name))
            return {
                "customer_name": cached_name,
                "current_state": "PICKUP_AWAITING_ITEMS",
                "response_sent": True
            }
    else:
        send_text_message(state["phone_number"], t("ASK_NAME", lang))
        return {
            "pending_items_input": state["text_input"] if is_direct_order else "",
            "current_state": "PICKUP_AWAITING_NAME",
            "response_sent": True
        }

def pickup_items_node(state: BotState) -> Dict[str, Any]:
    """
    Processes listed clothes using Gemini and generates estimates.
    """
    lang = state["language"]
    text = state["text_input"]
    
    # Send text to Gemini to parse garments
    estimate_data = generate_estimate(text, lang)
    
    # 1. Check if conversational interrupt/question
    if estimate_data.get("is_question"):
        send_text_message(state["phone_number"], f"{estimate_data.get('reply')}{t('ESTIMATE_QUESTION_SUFFIX', lang)}")
        return {
            "current_state": "PICKUP_AWAITING_ITEMS",
            "response_sent": True
        }
        
    total_count = estimate_data.get("total_items_count", 0)
    base_estimate = estimate_data.get("base_estimate", 0.0)
    identified_services = estimate_data.get("identified_services", ["Dry Clean"])
    
    if total_count == 0:
        send_text_message(state["phone_number"], t("ITEMS_UNDERSTANDING_ERROR", lang))
        return {
            "current_state": "PICKUP_AWAITING_ITEMS",
            "response_sent": True
        }
        
    # Check Loyalty Delivery discount
    db = SessionLocal()
    monthly_orders = get_monthly_order_count(db, state["customer_id"])
    db.close()
    
    if monthly_orders >= 4:
        delivery_fee = 0.0
        delivery_str = "₹0"
        promo_msg = t("LOYALTY_BONUS_PROMO", lang)
    else:
        delivery_fee = 30.0
        delivery_str = "₹30"
        promo_msg = ""
        
    final_estimate = base_estimate + delivery_fee
    
    # Store temporary variables to state
    update_dict = {
        "item_count": total_count,
        "base_estimate": base_estimate,
        "delivery_fee": delivery_fee,
        "delivery_str": delivery_str,
        "promo_msg": promo_msg,
        "final_estimate": final_estimate,
        "garments_list": estimate_data.get("garments", [])
    }
     # Check Ashirwad Points balance
    db = SessionLocal()
    available_points = get_available_points(db, state["customer_id"])
    db.close()
    
    prefix = state.get("direct_order_prefix", "")
    
    if available_points >= 50:
        max_redeemable = min(available_points, int(final_estimate))
        update_dict["max_redeemable"] = max_redeemable
        
        combined_msg = prefix + t("POINTS_OFFER", lang, 
                          promo_msg=promo_msg, 
                          total_count=total_count, 
                          base_estimate=base_estimate, 
                          delivery_str=delivery_str, 
                          final_estimate=final_estimate, 
                          available_points=available_points, 
                          max_redeemable=max_redeemable)
        buttons = [
            {"id": "btn_redeem_yes", "title": t("POINTS_BUTTON_YES", lang, max_redeemable=max_redeemable)},
            {"id": "btn_redeem_no", "title": t("POINTS_BUTTON_NO", lang)}
        ]
        send_interactive_buttons(state["phone_number"], combined_msg, buttons)
        update_dict["current_state"] = "PICKUP_AWAITING_POINTS_REDEEM"
        update_dict["response_sent"] = True
        update_dict["direct_order_prefix"] = ""
        return update_dict

    # No points, proceed directly to address
    update_dict["points_redeemed"] = 0
    update_dict["direct_order_prefix"] = ""
    return trigger_address_verification(state, update_dict)

def trigger_address_verification(state: BotState, state_updates: dict) -> dict:
    """Helper to query address details and send selection buttons"""
    lang = state["language"]
    
    db = SessionLocal()
    saved_address = get_customer_saved_address(db, state["customer_id"])
    db.close()
    
    # Fetch parameters from updates or fallback to state
    base_estimate = state_updates.get("base_estimate", state.get("base_estimate", 0.0))
    delivery_str = state_updates.get("delivery_str", state.get("delivery_str", "₹30"))
    promo_msg = state_updates.get("promo_msg", state.get("promo_msg", ""))
    final_estimate = state_updates.get("final_estimate", state.get("final_estimate", 0.0))
    points_redeemed = state_updates.get("points_redeemed", state.get("points_redeemed", 0))
    
    prefix = state_updates.get("direct_order_prefix", state.get("direct_order_prefix", ""))
    
    if points_redeemed > 0:
        final_estimate -= points_redeemed
        promo_msg += t("POINTS_APPLIED_MSG", lang, points_redeemed=points_redeemed)
        
    state_updates["final_estimate"] = final_estimate
    state_updates["promo_msg"] = promo_msg
    
    if saved_address:
        state_updates["saved_address"] = saved_address
        combined_msg = prefix + t("ADDRESS_CONFIRMATION_SAVED", lang,
                         base_estimate=base_estimate,
                         delivery_str=delivery_str,
                         promo_msg=promo_msg,
                         final_estimate=final_estimate,
                         saved_address=saved_address)
        buttons = [
            {"id": "btn_addr_yes", "title": t("ADDRESS_BUTTON_YES", lang)},
            {"id": "btn_addr_new", "title": t("ADDRESS_BUTTON_NEW", lang)}
        ]
        send_interactive_buttons(state["phone_number"], combined_msg, buttons)
        state_updates["current_state"] = "PICKUP_AWAITING_ADDRESS_BUTTON"
    else:
        combined_msg = prefix + t("ADDRESS_CONFIRMATION_NEW", lang,
                         base_estimate=base_estimate,
                         delivery_str=delivery_str,
                         promo_msg=promo_msg,
                         final_estimate=final_estimate)
        send_text_message(state["phone_number"], combined_msg)
        state_updates["current_state"] = "PICKUP_AWAITING_CONFIRMATION_ADDRESS"
        
    state_updates["direct_order_prefix"] = ""
    state_updates["response_sent"] = True
    return state_updates

def pickup_points_node(state: BotState) -> Dict[str, Any]:
    """
    Handles redemption selection.
    """
    lang = state["language"]
    text = state["text_input"]
    
    button_id = match_button_synonym(text, state["current_state"])
    points_redeemed = 0
    
    if button_id == "btn_redeem_yes":
        points_redeemed = state.get("max_redeemable", 0)
    elif button_id == "btn_redeem_no":
        points_redeemed = 0
    else:
        send_text_message(state["phone_number"], t("BUTTON_SELECTION_ERROR", lang))
        return {"response_sent": True}
        
    updates = {"points_redeemed": points_redeemed}
    return trigger_address_verification(state, updates)

def pickup_address_node(state: BotState) -> Dict[str, Any]:
    """
    Handles address verification and Paldi boundaries validation. Creates orders.
    """
    lang = state["language"]
    text = state["text_input"]
    curr_state = state["current_state"]
    
    flat_address = ""
    
    # A. Saved Address Confirmation Button
    if curr_state == "PICKUP_AWAITING_ADDRESS_BUTTON":
        button_id = match_button_synonym(text, curr_state)
        
        if button_id == "btn_addr_yes":
            flat_address = state.get("saved_address")
        elif button_id == "btn_addr_new":
            send_text_message(state["phone_number"], t("ADDRESS_INPUT_NEW_REQUEST", lang))
            return {
                "current_state": "PICKUP_AWAITING_CONFIRMATION_ADDRESS",
                "response_sent": True
            }
        else:
            # Fallback: if they typed their address directly (length > 5)
            if len(text.strip()) > 5:
                curr_state = "PICKUP_AWAITING_CONFIRMATION_ADDRESS"
            else:
                send_text_message(state["phone_number"], t("BUTTON_SELECTION_ERROR", lang))
                return {"response_sent": True}
            
    # B. Typing New Address or sharing Location GPS Pin
    if curr_state == "PICKUP_AWAITING_CONFIRMATION_ADDRESS":
        user_input = text.strip()
        flat_address = user_input
        
        is_gps = False
        lat_val, lon_val = 0.0, 0.0
        try:
            parts = flat_address.split(",")
            if len(parts) == 2:
                lat_val = float(parts[0])
                lon_val = float(parts[1])
                is_gps = True
        except ValueError:
            pass
            
        if not is_gps and ("google.com/maps" in flat_address or "maps.google.com" in flat_address):
            coords = extract_coords_from_url(flat_address)
            if coords:
                lat_val, lon_val = coords
                is_gps = True
                
        # Validate coordinates/address limits
        db = SessionLocal()
        if is_gps or "google.com/maps" in flat_address or "maps.google.com" in flat_address:
            if is_gps:
                if not is_in_paldi_coordinate(lat_val, lon_val):
                    send_text_message(state["phone_number"], t("OUTSIDE_PALDI_GPS", lang))
                    db.close()
                    return {"response_sent": True}
                update_customer_location(db, state["customer_id"], f"https://www.google.com/maps/search/?api=1&query={lat_val},{lon_val}")
            else:
                if not is_in_paldi_text(flat_address):
                    send_text_message(state["phone_number"], t("OUTSIDE_PALDI_TEXT", lang))
                    db.close()
                    return {"response_sent": True}
                update_customer_location(db, state["customer_id"], flat_address)
            flat_address = "Provided via GPS Pin"
        else:
            # Text check
            if not is_in_paldi_text(flat_address):
                send_text_message(state["phone_number"], t("OUTSIDE_PALDI_TEXT", lang))
                db.close()
                return {"response_sent": True}
            update_customer_saved_address(db, state["customer_id"], flat_address)
        db.close()
        
    # C. CREATE ORDER & CLEAR STATE
    db = SessionLocal()
    order = create_order(
        db, 
        state["customer_id"], 
        state["item_count"], 
        order_type="PICKUP",
        service_category=", ".join(list(set([g["service_category"] for g in state["garments_list"] if "service_category" in g])) or ["Dry Clean"]),
        flat_address=flat_address,
        estimated_amount=state["base_estimate"],
        delivery_fee=state["delivery_fee"],
        points_redeemed=state["points_redeemed"],
        special_instructions="None", 
        disclaimer_accepted=True,
        garments_list=state["garments_list"]
    )
    order_id = order.order_id
    db.close()
    
    send_text_message(state["phone_number"], t("ORDER_SUCCESS", lang, order_id=order_id))
    
    return {
        "current_flow": "IDLE",
        "current_state": "",
        "garments_list": [],
        "item_count": 0,
        "points_redeemed": 0,
        "saved_address": "",
        "response_sent": True
    }

def pricing_node(state: BotState) -> Dict[str, Any]:
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

def change_language_node(state: BotState) -> Dict[str, Any]:
    """
    Prompts the user to select their preferred language.
    """
    buttons = [
        {"id": "btn_lang_english", "title": "English"},
        {"id": "btn_lang_hinglish", "title": "Hindi (Hinglish)"},
        {"id": "btn_lang_gujlish", "title": "Gujarati (Gujlish)"}
    ]
    # Default to ENGLISH so t() outputs the combined multi-lingual text
    send_interactive_buttons(state["phone_number"], t("ASK_LANGUAGE", "ENGLISH"), buttons)
    
    return {
        "current_flow": "IDLE",
        "current_state": "AWAITING_LANGUAGE_SELECTION",
        "response_sent": True
    }

def status_node(state: BotState) -> Dict[str, Any]:
    """
    Shows status of user's active orders.
    """
    lang = state["language"]
    
    db = SessionLocal()
    orders = get_active_orders(db, state["customer_id"])
    db.close()
    
    if not orders:
        send_text_message(state["phone_number"], t("STATUS_NO_ORDERS", lang))
    elif len(orders) == 1:
        order = orders[0]
        send_text_message(state["phone_number"], t("STATUS_SINGLE_ORDER", lang, order_id=order.order_id, status_name=order.status.name))
    else:
        msg = t("STATUS_MULTIPLE_ORDERS", lang)
        for o in orders:
            msg += f"- #{o.order_id}: {o.status.name}\n"
        send_text_message(state["phone_number"], msg)
        
    return {
        "current_flow": "IDLE",
        "current_state": "",
        "response_sent": True
    }

def qa_node(state: BotState) -> Dict[str, Any]:
    """
    Resolves conversational queries / interruptions. Resumes flow if paused.
    """
    # Simply redirect queries to Gemini route
    lang = state["language"]
    text = state["text_input"]
    
    estimate_data = generate_estimate(text, lang)
    reply = estimate_data.get("reply", "I'm not sure how to answer that.")
    
    # Send answer
    send_text_message(state["phone_number"], reply)
    
    # Resume check
    if state.get("last_active_state"):
        # Put user back to the paused state
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

# ----------------- ROUTING CONDITIONAL EDGES -----------------

def route_next_node(state: BotState) -> str:
    """
    Directs the execution flow dynamically based on state variables.
    """
    flow = state.get("current_flow", "IDLE")
    curr_state = state.get("current_state", "")
    logger.info(f"[route_next_node] Evaluating routing. Flow: {flow}, State: {curr_state}")
    
    if flow == "GREETING":
        return "greeting"
    elif flow == "STATUS":
        return "status"
    elif flow == "PRICING":
        return "pricing"
    elif flow == "QA":
        return "qa"
    elif flow == "CHANGE_LANGUAGE":
        return "change_language"
    elif flow == "PICKUP":
        if not curr_state or curr_state == "INTENT_PICKUP":
            return "pickup_name"
        elif curr_state == "PICKUP_AWAITING_NAME":
            return "pickup_name"
        elif curr_state == "PICKUP_AWAITING_ITEMS":
            return "pickup_items"
        elif curr_state == "PICKUP_AWAITING_POINTS_REDEEM":
            return "pickup_points"
        elif curr_state in ["PICKUP_AWAITING_ADDRESS_BUTTON", "PICKUP_AWAITING_CONFIRMATION_ADDRESS"]:
            return "pickup_address"
            
    return END

# ----------------- COMPILE THE STATE GRAPH -----------------

def route_after_node(state: BotState) -> str:
    """
    Decides whether to terminate the graph run (if response was sent) 
    or continue routing within the same turn.
    """
    if state.get("response_sent"):
        logger.info("[route_after_node] Response sent to user. Terminating graph execution run (END).")
        return END
    next_node = route_next_node(state)
    logger.info(f"[route_after_node] Response not sent yet. Routing immediately to next node: '{next_node}'")
    return next_node

builder = StateGraph(BotState)

# Add Nodes
builder.add_node("classifier", classifier_node)
builder.add_node("greeting", greeting_node)
builder.add_node("pickup_name", pickup_name_node)
builder.add_node("pickup_items", pickup_items_node)
builder.add_node("pickup_points", pickup_points_node)
builder.add_node("pickup_address", pickup_address_node)
builder.add_node("pricing", pricing_node)
builder.add_node("status", status_node)
builder.add_node("qa", qa_node)
builder.add_node("change_language", change_language_node)

# Add Edges
builder.add_edge(START, "classifier")

# Conditional Router Edge from Classifier
builder.add_conditional_edges(
    "classifier",
    route_next_node,
    {
        "greeting": "greeting",
        "status": "status",
        "pricing": "pricing",
        "qa": "qa",
        "change_language": "change_language",
        "pickup_name": "pickup_name",
        "pickup_items": "pickup_items",
        "pickup_points": "pickup_points",
        "pickup_address": "pickup_address",
        END: END
    }
)

# Conditional Router Edges from All Flow Nodes
nodes_to_route = ["greeting", "pickup_name", "pickup_items", "pickup_points", "pickup_address", "pricing", "status", "qa", "change_language"]
for node in nodes_to_route:
    builder.add_conditional_edges(
        node,
        route_after_node,
        {
            "greeting": "greeting",
            "status": "status",
            "pricing": "pricing",
            "qa": "qa",
            "change_language": "change_language",
            "pickup_name": "pickup_name",
            "pickup_items": "pickup_items",
            "pickup_points": "pickup_points",
            "pickup_address": "pickup_address",
            END: END
        }
    )

# Persistent SQLite thread checkpointer (shared across all worker processes)
DB_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHECKPOINTS_DB = os.path.join(DB_DIR, "checkpoints.db")
conn = sqlite3.connect(CHECKPOINTS_DB, check_same_thread=False)
memory = SqliteSaver(conn)
compiled_graph = builder.compile(checkpointer=memory)
