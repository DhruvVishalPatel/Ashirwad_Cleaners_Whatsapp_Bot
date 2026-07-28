import os
import json
from app.services.whatsapp_sender import send_text_message, send_interactive_buttons
from app.core.state_machine import set_session_state, update_session_data, clear_session
from app.services.crud import create_order, update_customer_location, update_customer_name, get_customer_saved_address, update_customer_saved_address, get_monthly_order_count, get_available_points
from app.core.llm_router import generate_estimate
from app.models.schemas import Customer

def get_customer_name(db, customer_id: int):
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    return customer.name if customer else None

def handle_pickup_flow(phone_number: str, text: str, db, session_data: dict = None):
    current_state = session_data.get("state") if session_data else None
    data = session_data.get("data", {}) if session_data else {}
    customer_id = data.get("customer_id")
    
    # 1. New Pickup Intent -> Name Caching or Ask Name
    if not current_state or current_state == "INTENT_PICKUP":
        cached_name = get_customer_name(db, customer_id)
        
        if cached_name:
            # Skip name step!
            send_text_message(phone_number, f"Welcome back, {cached_name}! Please list the specific clothes you have and what service they need (e.g., 4 shirts for dry clean, 2 pants for washing).")
            set_session_state(phone_number, "PICKUP_AWAITING_ITEMS", data)
        else:
            send_text_message(phone_number, "Great! We'd love to pick up your clothes. What is your name?")
            set_session_state(phone_number, "PICKUP_AWAITING_NAME", data)
        return
        
    # 2. Name Received -> Ask for Itemized List
    if current_state == "PICKUP_AWAITING_NAME":
        name = text.strip()
        update_customer_name(db, customer_id, name)
        
        send_text_message(phone_number, f"Thanks {name}! Please list the specific clothes you have and what service they need (e.g., 4 shirts for dry clean, 2 pants for washing).")
        set_session_state(phone_number, "PICKUP_AWAITING_ITEMS", data)
        return
        
    # 3. Items Received -> LLM Estimate & The Master Confirmation Message
    if current_state == "PICKUP_AWAITING_ITEMS":
        # Call the LLM with the text to parse the item list OR answer a question
        estimate_data = generate_estimate(text)
        
        # --- NEW CONVERSATIONAL INTERRUPT LOGIC ---
        if estimate_data.get("is_question"):
            # The AI answered a question. Send the reply and DO NOT change the state.
            send_text_message(phone_number, f"{estimate_data.get('reply')}\n\nWhen you're ready, please list the specific clothes you have for pickup!")
            return
            
        total_count = estimate_data.get("total_items_count", 0)
        base_estimate = estimate_data.get("base_estimate", 0.0)
        identified_services = estimate_data.get("identified_services", ["Dry Clean"])
        
        if total_count == 0:
            send_text_message(phone_number, "I couldn't understand the items. Could you please list them out clearly? (e.g., '3 shirts for washing')")
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
            promo_msg = "🎉 *Loyalty Bonus*: Since this is your 5th+ order this month, your ₹30 Delivery Fee is completely waived!\n\n"
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
            
            combined_msg = (
                f"{promo_msg}"
                f"Your estimated bill for {total_count} items is approx ₹{base_estimate} + {delivery_str} (Delivery) = ₹{final_estimate}.\n\n"
                f"🎁 You have **{available_points} Ashirwad Points** available!\n"
                f"Would you like to redeem {max_redeemable} points for a ₹{max_redeemable} discount on this order?"
            )
            buttons = [
                {"id": "btn_redeem_yes", "title": f"✅ Redeem ₹{max_redeemable}"},
                {"id": "btn_redeem_no", "title": "❌ Save for later"}
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
        points_redeemed = 0
        if text == "btn_redeem_yes":
            points_redeemed = data.get("max_redeemable", 0)
            update_session_data(phone_number, "points_redeemed", points_redeemed)
        elif text == "btn_redeem_no":
            update_session_data(phone_number, "points_redeemed", 0)
        else:
            send_text_message(phone_number, "Please tap one of the buttons.")
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
        if text == "btn_addr_yes":
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
            
            send_text_message(phone_number, f"Thank you! Your order {order.order_id} has been created successfully. We will be at your location soon!")
            clear_session(phone_number)
            return
            
        elif text == "btn_addr_new":
            send_text_message(phone_number, "Please reply with your new exact address (Flat/House Number and Building Name) or share your WhatsApp location pin.")
            set_session_state(phone_number, "PICKUP_AWAITING_CONFIRMATION_ADDRESS", data)
            return
        else:
            send_text_message(phone_number, "Please tap one of the buttons.")
            return

    # 5. Address Received (New Address) -> Create Order!
    if current_state == "PICKUP_AWAITING_CONFIRMATION_ADDRESS":
        user_input = text.strip()
        flat_address = user_input
        
        # Check if it's a GPS pin (lat,long) from WhatsApp
        is_gps = False
        try:
            parts = flat_address.split(",")
            if len(parts) == 2:
                float(parts[0])
                float(parts[1])
                is_gps = True
        except ValueError:
            pass
            
        if "google.com/maps" in flat_address or is_gps:
            if is_gps:
                update_customer_location(db, customer_id, f"https://www.google.com/maps/search/?api=1&query={flat_address}")
            else:
                update_customer_location(db, customer_id, flat_address)
            flat_address = "Provided via GPS Pin"
        else:
            # Only save text address if it's actual text
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
        
        send_text_message(phone_number, f"Thank you! Your order {order.order_id} has been created successfully. We will be at your location soon!")
        clear_session(phone_number)
        return

def request_address_confirmation(phone_number, db, customer_id, data, promo_msg, total_count, base_estimate, delivery_str, final_estimate):
    saved_address = get_customer_saved_address(db, customer_id)
    points_redeemed = data.get("points_redeemed", 0)
    
    if points_redeemed > 0:
        final_estimate -= points_redeemed
        promo_msg += f"✅ **Points Applied**: -₹{points_redeemed} discount!\n"
        
    if saved_address:
        update_session_data(phone_number, "saved_address", saved_address)
        combined_msg = (
            f"👕 *Garments Estimate*: ₹{base_estimate}\n"
            f"🚚 *Delivery Charge*: {delivery_str}\n"
            f"{promo_msg}"
            f"**Total Estimate: ₹{final_estimate}**\n\n"
            f"*Policy Check*: Color, kasab, and zhumka work are handled at owner's risk.\n\n"
            f"🏠 We will pick this up from your saved address:\n*{saved_address}*"
        )
        buttons = [
            {"id": "btn_addr_yes", "title": "✅ Yes, use this"},
            {"id": "btn_addr_new", "title": "📝 New Address"}
        ]
        send_interactive_buttons(phone_number, combined_msg, buttons)
        set_session_state(phone_number, "PICKUP_AWAITING_ADDRESS_BUTTON", data)
    else:
        combined_msg = (
            f"👕 *Garments Estimate*: ₹{base_estimate}\n"
            f"🚚 *Delivery Charge*: {delivery_str}\n"
            f"{promo_msg}"
            f"**Total Estimate: ₹{final_estimate}**\n\n"
            f"*Policy Check*: Color, kasab, and zhumka work are handled at owner's risk.\n\n"
            f"📍 **Note: We currently ONLY offer pickup and delivery in the Paldi area.**\n\n"
            f"To accept this policy and confirm your order, please reply with your exact Paldi address (Flat/House Number and Building Name) or share your WhatsApp location pin."
        )
        send_text_message(phone_number, combined_msg)
        set_session_state(phone_number, "PICKUP_AWAITING_CONFIRMATION_ADDRESS", data)
