import re
from typing import Dict, Any
from app.core.database import SessionLocal
from app.models.schemas import Customer
from app.services.whatsapp_sender import send_text_message, send_interactive_buttons
from app.core.translations import t
from app.core.llm_router import generate_estimate
from app.core.logger import logger
from app.services.crud import (
    create_order,
    update_customer_location,
    update_customer_name,
    get_customer_saved_address,
    update_customer_saved_address,
    get_monthly_order_count,
    get_available_points
)

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

def pickup_name_node(state: dict) -> Dict[str, Any]:
    """
    Asks the customer for their name if not already cached.
    Supports directly parsing garments from the initial message.
    """
    lang = state["language"]
    input_text = state["text_input"].strip()
    clean_input = input_text.lower()
    is_direct_order = not (clean_input in ["pickup", "btn_intent_pickup", "order", "book", "laundry", "dry clean", "steam press"])
    
    if state.get("current_state") == "PICKUP_AWAITING_NAME":
        if input_text.startswith("btn_"):
            send_text_message(state["phone_number"], t("ASK_NAME", lang))
            return {
                "current_state": "PICKUP_AWAITING_NAME",
                "response_sent": True
            }
            
        name = input_text
        with SessionLocal() as db:
            update_customer_name(db, state["customer_id"], name)
        
        pending_items = state.get("pending_items_input")
        if pending_items:
            return {
                "customer_name": name,
                "text_input": pending_items,
                "pending_items_input": "",
                "direct_order_prefix": t("NEW_CUSTOMER_PREFIX", lang, name=name),
                "current_state": "PICKUP_AWAITING_ITEMS",
                "response_sent": False
            }
            
        send_text_message(state["phone_number"], t("WELCOME_BACK", lang, name=name))
        return {
            "customer_name": name,
            "current_state": "PICKUP_AWAITING_ITEMS",
            "response_sent": True
        }
        
    cached_name = None
    with SessionLocal() as db:
        customer = db.query(Customer).filter(Customer.customer_id == state["customer_id"]).first()
        if customer:
            cached_name = customer.name
    
    if cached_name:
        if is_direct_order:
            return {
                "customer_name": cached_name,
                "direct_order_prefix": t("WELCOME_BACK_PREFIX", lang, name=cached_name),
                "current_state": "PICKUP_AWAITING_ITEMS",
                "response_sent": False
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

def pickup_items_node(state: dict) -> Dict[str, Any]:
    """
    Processes listed clothes using Gemini and generates estimates.
    Supports merging additions ("add 3 pants") or replacing items.
    """
    lang = state["language"]
    text = state["text_input"]
    clean_text = text.strip().lower()
    
    estimate_data = generate_estimate(text, lang)
    
    if estimate_data.get("is_question"):
        send_text_message(state["phone_number"], f"{estimate_data.get('reply')}{t('ESTIMATE_QUESTION_SUFFIX', lang)}")
        return {
            "current_state": "PICKUP_AWAITING_ITEMS",
            "response_sent": True
        }
        
    new_garments = estimate_data.get("garments", [])
    existing_garments = state.get("garments_list", [])
    
    if not new_garments and not existing_garments:
        send_text_message(state["phone_number"], t("ITEMS_UNDERSTANDING_ERROR", lang))
        return {
            "current_state": "PICKUP_AWAITING_ITEMS",
            "response_sent": True
        }
        
    is_addition = clean_text.startswith("add ") or "add " in clean_text or clean_text.startswith("plus ") or clean_text.startswith("include ")
    is_removal = clean_text.startswith("remove ") or "remove " in clean_text or clean_text.startswith("nikal ") or clean_text.startswith("hatao ")

    if is_addition and existing_garments and new_garments:
        merged_garments = list(existing_garments) + new_garments
    elif is_removal and existing_garments and new_garments:
        remove_names = set(g.get("normalized_name", "").lower() for g in new_garments)
        merged_garments = [g for g in existing_garments if g.get("normalized_name", "").lower() not in remove_names]
    else:
        merged_garments = new_garments if new_garments else existing_garments

    total_count = sum(g.get("quantity", 1) for g in merged_garments)
    
    base_estimate = 0.0
    with SessionLocal() as db:
        from app.models.schemas import CatalogItem
        items_db = db.query(CatalogItem).all()
        price_map = {(ci.service_type, ci.item_name): ci.price for ci in items_db}
        for g in merged_garments:
            cat = g.get("service_category", "dry_clean")
            name = g.get("normalized_name", "")
            qty = g.get("quantity", 1)
            p = price_map.get((cat, name), price_map.get(("dry_clean", name), 50.0))
            base_estimate += (p * qty)

    with SessionLocal() as db:
        monthly_orders = get_monthly_order_count(db, state["customer_id"])
    
    if monthly_orders >= 4:
        delivery_fee = 0.0
        delivery_str = "₹0"
        promo_msg = t("LOYALTY_BONUS_PROMO", lang)
    else:
        delivery_fee = 30.0
        delivery_str = "₹30"
        promo_msg = ""
        
    final_estimate = base_estimate + delivery_fee
    
    update_dict = {
        "item_count": total_count,
        "base_estimate": base_estimate,
        "delivery_fee": delivery_fee,
        "delivery_str": delivery_str,
        "promo_msg": promo_msg,
        "final_estimate": final_estimate,
        "garments_list": merged_garments
    }
    
    with SessionLocal() as db:
        available_points = get_available_points(db, state["customer_id"])
    
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

    update_dict["points_redeemed"] = 0
    update_dict["direct_order_prefix"] = ""
    return trigger_address_verification(state, update_dict)

def trigger_address_verification(state: dict, state_updates: dict) -> dict:
    """Helper to query address details and send selection buttons"""
    lang = state["language"]
    
    saved_address = None
    with SessionLocal() as db:
        saved_address = get_customer_saved_address(db, state["customer_id"])
    
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

def pickup_points_node(state: dict) -> Dict[str, Any]:
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

def pickup_address_node(state: dict) -> Dict[str, Any]:
    """
    Handles address verification and Paldi boundaries validation. Creates orders.
    """
    lang = state["language"]
    text = state["text_input"]
    curr_state = state["current_state"]
    flat_address = ""
    
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
            clean_text = text.strip().lower()
            if (clean_text.startswith("add ") or "add " in clean_text or 
                clean_text.startswith("remove ") or clean_text.startswith("change ") or
                "pant" in clean_text or "shirt" in clean_text or "saree" in clean_text or "wash" in clean_text or "dry clean" in clean_text):
                return {
                    "text_input": text,
                    "current_state": "PICKUP_AWAITING_ITEMS",
                    "response_sent": False
                }
            if len(text.strip()) > 5:
                curr_state = "PICKUP_AWAITING_CONFIRMATION_ADDRESS"
            else:
                send_text_message(state["phone_number"], t("BUTTON_SELECTION_ERROR", lang))
                return {"response_sent": True}
            
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
                
        with SessionLocal() as db:
            if is_gps or "google.com/maps" in flat_address or "maps.google.com" in flat_address:
                if is_gps:
                    if not is_in_paldi_coordinate(lat_val, lon_val):
                        send_text_message(state["phone_number"], t("OUTSIDE_PALDI_GPS", lang))
                        return {"response_sent": True}
                    update_customer_location(db, state["customer_id"], f"https://www.google.com/maps/search/?api=1&query={lat_val},{lon_val}")
                else:
                    if not is_in_paldi_text(flat_address):
                        send_text_message(state["phone_number"], t("OUTSIDE_PALDI_TEXT", lang))
                        return {"response_sent": True}
                    update_customer_location(db, state["customer_id"], flat_address)
                flat_address = "Provided via GPS Pin"
            else:
                if not is_in_paldi_text(flat_address):
                    send_text_message(state["phone_number"], t("OUTSIDE_PALDI_TEXT", lang))
                    return {"response_sent": True}
                update_customer_saved_address(db, state["customer_id"], flat_address)
        
    with SessionLocal() as db:
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
