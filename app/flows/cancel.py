import re
from typing import Dict, Any, Optional
from app.core.database import SessionLocal
from app.models.schemas import Order, OrderStatus
from app.services.crud import clean_order_id, add_points_transaction, get_active_orders
from app.services.whatsapp_sender import send_text_message, send_interactive_buttons
from app.core.translations import t
from app.flows.status import format_status_display

def extract_order_id_from_text(text: str) -> Optional[str]:
    """
    Extracts an order ID if present in strings like:
    'cancel 1029', '1029', 'cancel order #1029', 'order 1029 cancel'
    """
    clean = text.strip()
    match = re.search(r'\b(?:cancel\s*(?:order\s*)?(?:#\s*)?)?(\d{4,})\b', clean, re.IGNORECASE)
    if match:
        return match.group(1)
    # Check if the entire text is just digits (like '1029')
    if clean.isdigit():
        return clean
    return None

def match_cancel_synonym(text: str) -> str:
    clean = text.strip().lower()
    if clean.startswith("btn_confirm_cancel"):
        return "btn_confirm_cancel"
    if clean == "btn_keep_order":
        return "btn_keep_order"
        
    yes_syns = ["yes", "y", "yeah", "ok", "okay", "sure", "cancel", "cancel karo", "haan", "ha", "confirm", "radd karo", "chodi do", "please cancel"]
    no_syns = ["no", "n", "nope", "keep", "keep order", "rehne do", "nahi", "na", "mat karo", "reva do", "don't cancel", "order rakho"]
    if clean in yes_syns:
        return "btn_confirm_cancel"
    if clean in no_syns:
        return "btn_keep_order"
        
    if any(s in clean for s in ["yes", "cancel", "haan", "confirm", "radd"]):
        return "btn_confirm_cancel"
    if any(s in clean for s in ["no", "keep", "nahi", "rehne", "mat"]):
        return "btn_keep_order"
        
    return clean

def cancel_node(state: dict) -> Dict[str, Any]:
    """
    Handles conversational order cancellation for existing placed orders.
    Customers may only cancel orders that are still in PENDING_PICKUP.
    """
    lang = state["language"]
    text = state.get("text_input", "").strip()
    curr_state = state.get("current_state", "")
    customer_id = state["customer_id"]

    # 1. Handling Confirmation response
    if curr_state == "CANCEL_AWAITING_CONFIRMATION":
        decision = match_cancel_synonym(text)
        target_order_id = state.get("cancel_order_id", "")
        clean_target_id = clean_order_id(target_order_id)

        if decision == "btn_confirm_cancel":
            with SessionLocal() as db:
                order = db.query(Order).filter(
                    Order.customer_id == customer_id,
                    (Order.order_id == clean_target_id) | (Order.order_id == target_order_id)
                ).first()

                if not order:
                    send_text_message(state["phone_number"], t("CANCEL_ORDER_NOT_FOUND", lang, order_id=clean_target_id))
                elif order.status != OrderStatus.PENDING_PICKUP:
                    status_str = format_status_display(order.status)
                    send_text_message(state["phone_number"], t("CANCEL_NOT_PENDING_PICKUP", lang, order_id=clean_target_id, status_str=status_str))
                else:
                    order.status = OrderStatus.CANCELLED
                    # Refund loyalty points if redeemed
                    if getattr(order, "points_redeemed", 0) and order.points_redeemed > 0:
                        add_points_transaction(db, customer_id, order.points_redeemed, "EARNED", order.order_id)
                    db.commit()

                    try:
                        from app.core.ws_manager import broadcast_event_sync
                        broadcast_event_sync("ORDER_UPDATED", {"order_id": order.order_id, "action": "status_updated", "status": "CANCELLED"})
                    except Exception:
                        pass

                    send_text_message(state["phone_number"], t("CANCEL_SUCCESS", lang, order_id=clean_target_id))

            return {
                "current_flow": "IDLE",
                "current_state": "",
                "cancel_order_id": "",
                "response_sent": True
            }

        elif decision == "btn_keep_order":
            send_text_message(state["phone_number"], t("CANCEL_ABORTED", lang, order_id=clean_target_id))
            return {
                "current_flow": "IDLE",
                "current_state": "",
                "cancel_order_id": "",
                "response_sent": True
            }

        else:
            # If user didn't give clear confirmation, re-prompt buttons
            with SessionLocal() as db:
                ord_obj = db.query(Order).filter(
                    Order.customer_id == customer_id,
                    (Order.order_id == clean_target_id) | (Order.order_id == target_order_id)
                ).first()
                item_cnt = ord_obj.item_count if ord_obj else 1
                cat = (ord_obj.service_category if ord_obj else "Laundry / Dry Clean") or "Laundry / Dry Clean"

            buttons = [
                {"id": f"btn_confirm_cancel_{clean_target_id}", "title": t("BTN_CONFIRM_CANCEL", lang, order_id=clean_target_id)},
                {"id": "btn_keep_order", "title": t("BTN_KEEP_ORDER", lang)}
            ]
            send_interactive_buttons(state["phone_number"], t("CANCEL_CONFIRM_PROMPT", lang, order_id=clean_target_id, item_count=item_cnt, service_category=cat), buttons)
            return {"response_sent": True}

    # 2. Extract potential Order ID from user text
    extracted_id = extract_order_id_from_text(text)

    with SessionLocal() as db:
        if extracted_id:
            clean_id = clean_order_id(extracted_id)
            order = db.query(Order).filter(
                Order.customer_id == customer_id,
                (Order.order_id == clean_id) | (Order.order_id == extracted_id)
            ).first()

            if not order:
                send_text_message(state["phone_number"], t("CANCEL_ORDER_NOT_FOUND", lang, order_id=clean_id))
                return {
                    "current_flow": "IDLE",
                    "current_state": "",
                    "cancel_order_id": "",
                    "response_sent": True
                }

            if order.status == OrderStatus.CANCELLED:
                send_text_message(state["phone_number"], t("CANCEL_ORDER_ALREADY_CANCELLED", lang, order_id=clean_id))
                return {
                    "current_flow": "IDLE",
                    "current_state": "",
                    "cancel_order_id": "",
                    "response_sent": True
                }

            if order.status != OrderStatus.PENDING_PICKUP:
                status_str = format_status_display(order.status)
                send_text_message(state["phone_number"], t("CANCEL_NOT_PENDING_PICKUP", lang, order_id=clean_id, status_str=status_str))
                return {
                    "current_flow": "IDLE",
                    "current_state": "",
                    "cancel_order_id": "",
                    "response_sent": True
                }

            # Prompt confirmation for this specific order
            buttons = [
                {"id": f"btn_confirm_cancel_{clean_id}", "title": t("BTN_CONFIRM_CANCEL", lang, order_id=clean_id)},
                {"id": "btn_keep_order", "title": t("BTN_KEEP_ORDER", lang)}
            ]
            category = order.service_category or "Laundry / Dry Clean"
            send_interactive_buttons(
                state["phone_number"],
                t("CANCEL_CONFIRM_PROMPT", lang, order_id=clean_id, item_count=order.item_count, service_category=category),
                buttons
            )
            return {
                "current_flow": "CANCEL",
                "current_state": "CANCEL_AWAITING_CONFIRMATION",
                "cancel_order_id": clean_id,
                "response_sent": True
            }

        # 3. No order ID provided: query customer's active orders
        pending_pickup_orders = db.query(Order).filter(
            Order.customer_id == customer_id,
            Order.status == OrderStatus.PENDING_PICKUP
        ).order_by(Order.created_at.desc()).all()

        if not pending_pickup_orders:
            all_active = get_active_orders(db, customer_id)
            if all_active:
                send_text_message(state["phone_number"], t("CANCEL_NO_PENDING_PICKUP", lang))
            else:
                send_text_message(state["phone_number"], t("CANCEL_NO_ACTIVE_ORDERS", lang))
            return {
                "current_flow": "IDLE",
                "current_state": "",
                "cancel_order_id": "",
                "response_sent": True
            }

        if len(pending_pickup_orders) == 1:
            # Exactly 1 active order pending pickup -> ask for confirmation!
            single_order = pending_pickup_orders[0]
            clean_id = clean_order_id(single_order.order_id)
            buttons = [
                {"id": f"btn_confirm_cancel_{clean_id}", "title": t("BTN_CONFIRM_CANCEL", lang, order_id=clean_id)},
                {"id": "btn_keep_order", "title": t("BTN_KEEP_ORDER", lang)}
            ]
            category = single_order.service_category or "Laundry / Dry Clean"
            send_interactive_buttons(
                state["phone_number"],
                t("CANCEL_CONFIRM_PROMPT", lang, order_id=clean_id, item_count=single_order.item_count, service_category=category),
                buttons
            )
            return {
                "current_flow": "CANCEL",
                "current_state": "CANCEL_AWAITING_CONFIRMATION",
                "cancel_order_id": clean_id,
                "response_sent": True
            }

        # Multiple cancellable orders -> list them and ask which one to cancel
        orders_lines = []
        for o in pending_pickup_orders:
            c_id = clean_order_id(o.order_id)
            orders_lines.append(f"• #{c_id}: Pending Pickup ({o.item_count} items - {o.service_category or 'Dry Clean'})")
        orders_list = "\n".join(orders_lines)
        sample_id = clean_order_id(pending_pickup_orders[0].order_id)

        send_text_message(
            state["phone_number"],
            t("CANCEL_MULTIPLE_CHOICE", lang, orders_list=orders_list, sample_id=sample_id)
        )
        return {
            "current_flow": "CANCEL",
            "current_state": "CANCEL_AWAITING_ORDER_SELECTION",
            "cancel_order_id": "",
            "response_sent": True
        }
