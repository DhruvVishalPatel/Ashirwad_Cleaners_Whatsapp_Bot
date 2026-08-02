import os
import json
from app.services.whatsapp_sender import send_text_message, send_interactive_buttons
from app.core.state_machine import set_session_state, update_session_data, clear_session
from app.services.crud import create_order, update_customer_location, update_customer_name, get_customer_saved_address, update_customer_saved_address, get_monthly_order_count, get_available_points
from app.core.llm_router import generate_estimate
from app.models.schemas import Customer
from app.core.translations import t

import re

def get_customer_name(db, customer_id: int):
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    return customer.name if customer else None

def match_button_synonym(text: str, state: str) -> str:
    clean_text = text.strip().lower()
    
    # If the user actually clicked the button, return the button ID directly
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
            
    return text  # Return original if no match

def extract_coords_from_url(url: str):
    # Matches patterns like q=23.0125,72.5654 or query=23.0125,72.5654
    match = re.search(r'(?:q|query|ll)=([+-]?\d+\.\d+),([+-]?\d+\.\d+)', url)
    if match:
        return float(match.group(1)), float(match.group(2))
    return None

def is_in_paldi_coordinate(lat: float, lon: float) -> bool:
    # Bounding box for Paldi area in Ahmedabad
    return (23.000 <= lat <= 23.028) and (72.550 <= lon <= 72.580)

def is_in_paldi_text(address: str) -> bool:
    return "paldi" in address.lower()

def handle_pickup_flow(phone_number: str, text: str, db, session_data: dict = None):
    current_state = session_data.get("state") if session_data else None
    data = session_data.get("data", {}) if session_data else {}
    customer_id = data.get("customer_id")
    
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    lang = customer.preferred_language if customer else "ENGLISH"
    
    # 1. New Pickup Intent -> Name Caching or Ask Name
    if not current_state or current_state == "INTENT_PICKUP":
        cached_name = get_customer_name(db, customer_id)
        
        if cached_name:
            # Skip name step!
            send_text_message(phone_number, t("WELCOME_BACK", lang, name=cached_name))
            set_session_state(phone_number, "PICKUP_AWAITING_ITEMS", data)
        else:
            send_text_message(phone_number, t("ASK_NAME", lang))
            set_session_state(phone_number, "PICKUP_AWAITING_NAME", data)
        return
        
    # 2. Name Received -> Ask for Itemized List
    if current_state == "PICKUP_AWAITING_NAME":
        name = text.strip()
        update_customer_name(db, customer_id, name)
        
        send_text_message(phone_number, t("WELCOME_BACK", lang, name=name))
        set_session_state(phone_number, "PICKUP_AWAITING_ITEMS", data)
        return
        
    # 3. Items Received -> LLM Estimate & The Master Confirmation Message
    if current_state == "PICKUP_AWAITING_ITEMS":
        # Call the LLM with the text to parse the item list OR answer a question
        estimate_data = generate_estimate(text, lang)
        
        # --- NEW CONVERSATIONAL INTERRUPT LOGIC ---
        if estimate_data.get("is_question"):
            # The AI answered a question. Send the reply and DO NOT change the state.
            send_text_message(phone_number, f"{estimate_data.get('reply')}{t('ESTIMATE_QUESTION_SUFFIX', lang)}")
            return
            
        total_count = estimate_data.get("total_items_count", 0)
        base_estimate = estimate_data.get("base_estimate", 0.0)
        identified_services = estimate_data.get("identified_services", ["Dry Clean"])
        
        if total_count == 0:
            send_text_message(phone_number, t("ITEMS_UNDERSTANDING_ERROR", lang))
            return
            
        update_session_data(phone_number, "count", total_count)
        update_session_data(phone_number, "estimate", base_estimate)
        update_session_data(phone_number, "service_category", ", ".join(identified_services))
        update_session_data(phone_number, "garments", estimate_data.get("garments", []))
        
        # Delivery Fee Loyalty Logic
        monthly_orders = get_monthly_order_count(db, customer_id)
        if monthly_orders >= 4:
            delivery_fee = 0.0
            delivery_str = "₹0"
            promo_msg = t("LOYALTY_BONUS_PROMO", lang)
        else:
            delivery_fee = 30.0
            delivery_str = "₹30"
            promo_msg = ""
            
        final_estimate = base_estimate + delivery_fee
        update_session_data(phone_number, "delivery_fee", delivery_fee)
        
        # --- NEW POINTS LOGIC ---
        available_points = get_available_points(db, customer_id)
        if available_points >= 50:
            # Offer points redemption
            max_redeemable = min(available_points, int(final_estimate))
            update_session_data(phone_number, "max_redeemable", max_redeemable)
            update_session_data(phone_number, "promo_msg", promo_msg)
            
            combined_msg = t("POINTS_OFFER", lang, 
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
            send_interactive_buttons(phone_number, combined_msg, buttons)
            set_session_state(phone_number, "PICKUP_AWAITING_POINTS_REDEEM", data)
            return

        # No points to redeem, skip straight to address
        update_session_data(phone_number, "points_redeemed", 0)
        request_address_confirmation(phone_number, db, customer_id, data, promo_msg, total_count, base_estimate, delivery_str, final_estimate)
        return
        
    # 4.5. Points Redemption Received
    if current_state == "PICKUP_AWAITING_POINTS_REDEEM":
        button_id = match_button_synonym(text, current_state)
        points_redeemed = 0
        if button_id == "btn_redeem_yes":
            points_redeemed = data.get("max_redeemable", 0)
            update_session_data(phone_number, "points_redeemed", points_redeemed)
        elif button_id == "btn_redeem_no":
            update_session_data(phone_number, "points_redeemed", 0)
        else:
            send_text_message(phone_number, t("BUTTON_SELECTION_ERROR", lang))
            return
            
        # Extract variables from data to pass to request_address_confirmation
        customer_id = data.get("customer_id")
        total_count = data.get("count", 0)
        base_estimate = data.get("estimate", 0.0)
        delivery_fee = data.get("delivery_fee", 30.0)
        delivery_str = "₹0" if delivery_fee == 0.0 else f"₹{delivery_fee}"
        final_estimate = base_estimate + delivery_fee
        promo_msg = data.get("promo_msg", "")
        request_address_confirmation(phone_number, db, customer_id, data, promo_msg, total_count, base_estimate, delivery_str, final_estimate)
        return

    # 4.5. Address Button Received
    if current_state == "PICKUP_AWAITING_ADDRESS_BUTTON":
        button_id = match_button_synonym(text, current_state)
        if button_id == "btn_addr_yes":
            flat_address = data.get("saved_address")
            
            count = data.get("count", 0)
            estimate = data.get("estimate", 0.0)
            delivery_fee = data.get("delivery_fee", 30.0)
            points_redeemed = data.get("points_redeemed", 0)
            service_category = data.get("service_category", "Dry Clean")
            garments = data.get("garments", [])
            order = create_order(
                db, 
                customer_id, 
                count, 
                order_type="PICKUP",
                service_category=service_category,
                flat_address=flat_address,
                estimated_amount=estimate,
                delivery_fee=delivery_fee,
                points_redeemed=points_redeemed,
                special_instructions="None", 
                disclaimer_accepted=True,
                garments_list=garments
            )
            
            send_text_message(phone_number, t("ORDER_SUCCESS", lang, order_id=order.order_id))
            clear_session(phone_number)
            return
            
        elif button_id == "btn_addr_new":
            send_text_message(phone_number, t("ADDRESS_INPUT_NEW_REQUEST", lang))
            set_session_state(phone_number, "PICKUP_AWAITING_CONFIRMATION_ADDRESS", data)
            return
        else:
            send_text_message(phone_number, t("BUTTON_SELECTION_ERROR", lang))
            return

    # 5. Address Received (New Address) -> Create Order!
    if current_state == "PICKUP_AWAITING_CONFIRMATION_ADDRESS":
        user_input = text.strip()
        flat_address = user_input
        
        # Check if it's a GPS pin (lat,long) from WhatsApp
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
            
        # Parse coordinates from Google Maps links if present
        if not is_gps and ("google.com/maps" in flat_address or "maps.google.com" in flat_address):
            coords = extract_coords_from_url(flat_address)
            if coords:
                lat_val, lon_val = coords
                is_gps = True
                
        # Validate coordinates/address limits
        if is_gps or "google.com/maps" in flat_address or "maps.google.com" in flat_address:
            if is_gps:
                if not is_in_paldi_coordinate(lat_val, lon_val):
                    send_text_message(phone_number, t("OUTSIDE_PALDI_GPS", lang))
                    return
                update_customer_location(db, customer_id, f"https://www.google.com/maps/search/?api=1&query={lat_val},{lon_val}")
            else:
                # Fallback check for URL queries
                if not is_in_paldi_text(flat_address):
                    send_text_message(phone_number, t("OUTSIDE_PALDI_TEXT", lang))
                    return
                update_customer_location(db, customer_id, flat_address)
            flat_address = "Provided via GPS Pin"
        else:
            # Text Address Check
            if not is_in_paldi_text(flat_address):
                send_text_message(phone_number, t("OUTSIDE_PALDI_TEXT", lang))
                return
            update_customer_saved_address(db, customer_id, flat_address)
            
        count = data.get("count", 0)
        estimate = data.get("estimate", 0.0)
        delivery_fee = data.get("delivery_fee", 30.0)
        points_redeemed = data.get("points_redeemed", 0)
        service_category = data.get("service_category", "Dry Clean")
        garments = data.get("garments", [])
        
        order = create_order(
            db, 
            customer_id, 
            count, 
            order_type="PICKUP",
            service_category=service_category,
            flat_address=flat_address,
            estimated_amount=estimate,
            delivery_fee=delivery_fee,
            points_redeemed=points_redeemed,
            special_instructions="None", 
            disclaimer_accepted=True,
            garments_list=garments
        )
        
        send_text_message(phone_number, t("ORDER_SUCCESS", lang, order_id=order.order_id))
        clear_session(phone_number)
        return

def request_address_confirmation(phone_number, db, customer_id, data, promo_msg, total_count, base_estimate, delivery_str, final_estimate):
    saved_address = get_customer_saved_address(db, customer_id)
    points_redeemed = data.get("points_redeemed", 0)
    
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    lang = customer.preferred_language if customer else "ENGLISH"
    
    if points_redeemed > 0:
        final_estimate -= points_redeemed
        promo_msg += t("POINTS_APPLIED_MSG", lang, points_redeemed=points_redeemed)
        
    if saved_address:
        update_session_data(phone_number, "saved_address", saved_address)
        combined_msg = t("ADDRESS_CONFIRMATION_SAVED", lang,
                         base_estimate=base_estimate,
                         delivery_str=delivery_str,
                         promo_msg=promo_msg,
                         final_estimate=final_estimate,
                         saved_address=saved_address)
        buttons = [
            {"id": "btn_addr_yes", "title": t("ADDRESS_BUTTON_YES", lang)},
            {"id": "btn_addr_new", "title": t("ADDRESS_BUTTON_NEW", lang)}
        ]
        send_interactive_buttons(phone_number, combined_msg, buttons)
        set_session_state(phone_number, "PICKUP_AWAITING_ADDRESS_BUTTON", data)
    else:
        combined_msg = t("ADDRESS_CONFIRMATION_NEW", lang,
                         base_estimate=base_estimate,
                         delivery_str=delivery_str,
                         promo_msg=promo_msg,
                         final_estimate=final_estimate)
        send_text_message(phone_number, combined_msg)
        set_session_state(phone_number, "PICKUP_AWAITING_CONFIRMATION_ADDRESS", data)
