import os
import sqlite3
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from app.core.database import SessionLocal
from app.models.schemas import Customer
from app.services.whatsapp_sender import send_text_message
from app.core.translations import t
from app.core.llm_router import classify_intent
from app.core.logger import logger

from app.flows.pickup import (
    pickup_name_node,
    pickup_items_node,
    pickup_points_node,
    pickup_address_node,
    match_button_synonym
)
from app.flows.pricing import pricing_node
from app.flows.status import status_node
from app.flows.qa import greeting_node, change_language_node, qa_node

# ----------------- STATE SCHEMA -----------------

class BotState(TypedDict):
    phone_number: str
    customer_id: int
    language: str              # "ENGLISH", "HINGLISH", "GUJLISH"
    current_flow: str          # "IDLE", "PICKUP", "PRICING", "STATUS", "QA"
    current_state: str         # Sub-state in flows
    last_active_state: str     # Backtracking / Resume location
    
    text_input: str
    response_sent: bool
    
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
    Decides intent, language, and potential backtracking requests.
    """
    text = state.get("text_input", "").strip()
    clean_text = text.lower()
    
    logger.info(f"[ClassifierNode] Entry. Current Flow: {state.get('current_flow')}, State: {state.get('current_state')}, Input: '{text}'")
    
    # 0. Reset turn flags
    state["response_sent"] = False

    # 1. Explicit Language Selection Buttons
    if text.startswith("btn_lang_"):
        lang_map = {
            "btn_lang_english": "ENGLISH",
            "btn_lang_hinglish": "HINGLISH",
            "btn_lang_gujlish": "GUJLISH"
        }
        selected_lang = lang_map.get(text, "ENGLISH")
        
        with SessionLocal() as db:
            customer = db.query(Customer).filter(Customer.customer_id == state["customer_id"]).first()
            if customer:
                customer.preferred_language = selected_lang
                db.commit()
        
        logger.info(f"[ClassifierNode] Language selected: {selected_lang}. Routing to GREETING flow.")
        return {
            "current_flow": "GREETING",
            "current_state": "",
            "last_active_state": "",
            "language": selected_lang,
            "response_sent": False
        }

    # 2. Global Reset Keywords
    reset_keywords = ["cancel", "restart", "start over", "reset", "radd", "cancel karo", "shuru se", "radd karo", "chodi do", "fari shuru karo"]
    if clean_text in reset_keywords:
        send_text_message(state["phone_number"], t("SESSION_CANCELLED", state.get("language", "ENGLISH")))
        return {
            "current_flow": "IDLE",
            "current_state": "",
            "last_active_state": "",
            "response_sent": True
        }

    # 3. Unspecified language fallback
    if not state.get("language") or state.get("language") not in ["ENGLISH", "HINGLISH", "GUJLISH"]:
        logger.info("[ClassifierNode] Unspecified language. Redirecting to CHANGE_LANGUAGE flow.")
        return {
            "current_flow": "CHANGE_LANGUAGE",
            "current_state": "",
            "last_active_state": "",
            "response_sent": False
        }
        
    # 4. Active flow check
    if state.get("current_flow") != "IDLE":
        if text.startswith("btn_"):
            return {"response_sent": False}
            
        if state.get("current_state") in ["PICKUP_AWAITING_NAME", "PICKUP_AWAITING_CONFIRMATION_ADDRESS"]:
            return {"response_sent": False}
            
        if state.get("current_state") in ["PICKUP_AWAITING_POINTS_REDEEM", "PICKUP_AWAITING_ADDRESS_BUTTON"]:
            syn = match_button_synonym(text, state["current_state"])
            if syn in ["btn_redeem_yes", "btn_redeem_no", "btn_addr_yes", "btn_addr_new"]:
                return {"response_sent": False}
                
        intent, detected_lang = classify_intent(text)
        
        if intent == "INTENT_GREETING":
            logger.info(f"[ClassifierNode] Greeting received during active flow '{state.get('current_flow')}'. Resetting state.")
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
            
        # Backtracking Modifiers
        if state.get("current_flow") == "PICKUP":
            backtrack_address = ["change address", "address badlo", "wrong address", "incorrect address", "naya address", "new address"]
            backtrack_name = ["change name", "naam badlo", "wrong name", "incorrect name"]
            
            is_item_modification = (
                clean_text.startswith("add ") or clean_text.startswith("remove ") or 
                clean_text.startswith("change ") or clean_text.startswith("edit ") or
                clean_text.startswith("nikal ") or clean_text.startswith("hatao ") or
                clean_text.startswith("plus ") or clean_text.startswith("minus ") or
                "add " in clean_text or "remove " in clean_text or "change items" in clean_text or 
                "change clothes" in clean_text or "items badlo" in clean_text or "kapde badlo" in clean_text
            )
            
            user_lang = state.get("language") if state.get("language") in ["ENGLISH", "HINGLISH", "GUJLISH"] else detected_lang
            if is_item_modification or (intent == "INTENT_PICKUP" and state.get("current_state") in ["PICKUP_AWAITING_POINTS_REDEEM", "PICKUP_AWAITING_ADDRESS_BUTTON", "PICKUP_AWAITING_CONFIRMATION_ADDRESS"]):
                return {
                    "language": user_lang,
                    "current_state": "PICKUP_AWAITING_ITEMS",
                    "text_input": text,
                    "response_sent": False
                }
            elif any(kw in clean_text for kw in backtrack_address):
                send_text_message(state["phone_number"], t("ADDRESS_INPUT_NEW_REQUEST", user_lang))
                return {
                    "language": user_lang,
                    "current_state": "PICKUP_AWAITING_CONFIRMATION_ADDRESS",
                    "saved_address": "",
                    "response_sent": True
                }
            elif any(kw in clean_text for kw in backtrack_name):
                send_text_message(state["phone_number"], t("ASK_NAME", user_lang))
                return {
                    "language": user_lang,
                    "current_state": "PICKUP_AWAITING_NAME",
                    "customer_name": "",
                    "response_sent": True
                }
                
        if intent == "INTENT_CHANGE_LANGUAGE":
            logger.info(f"[ClassifierNode] Change language requested during active flow '{state.get('current_flow')}'. Resetting state.")
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

        user_lang = state.get("language") if state.get("language") in ["ENGLISH", "HINGLISH", "GUJLISH"] else detected_lang
        if intent in ["INTENT_QA", "INTENT_PRICING"]:
            return {
                "language": user_lang,
                "current_flow": "QA",
                "last_active_state": state.get("current_state", ""),
                "response_sent": False
            }
            
        return {"response_sent": False}
        
    # 5. New Intent Routing
    if text == "btn_intent_pickup":
        intent, detected_lang = "INTENT_PICKUP", state["language"]
    elif text == "btn_intent_status":
        intent, detected_lang = "INTENT_STATUS", state["language"]
    elif text == "btn_intent_pricing":
        intent, detected_lang = "INTENT_PRICING", state["language"]
    else:
        intent, detected_lang = classify_intent(text)
        
    user_lang = state.get("language") if state.get("language") in ["ENGLISH", "HINGLISH", "GUJLISH"] else detected_lang
    if not state.get("language") and detected_lang:
        with SessionLocal() as db:
            customer = db.query(Customer).filter(Customer.customer_id == state["customer_id"]).first()
            if customer:
                customer.preferred_language = detected_lang
                db.commit()
    
    flow_mapping = {
        "INTENT_PICKUP": "PICKUP",
        "INTENT_STATUS": "STATUS",
        "INTENT_PRICING": "PRICING",
        "INTENT_GREETING": "GREETING",
        "INTENT_QA": "QA",
        "INTENT_CHANGE_LANGUAGE": "CHANGE_LANGUAGE"
    }
    
    next_flow = flow_mapping.get(intent, "QA")
    logger.info(f"[ClassifierNode] Output. Routed to Flow: {next_flow}, Language: {user_lang}")
    return {
        "current_flow": next_flow,
        "language": user_lang,
        "response_sent": False
    }

# ----------------- ROUTING CONDITIONAL EDGES -----------------

def route_next_node(state: BotState) -> str:
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

def route_after_node(state: BotState) -> str:
    if state.get("response_sent") or state.get("current_state") in ["PICKUP_AWAITING_ITEMS", "PICKUP_AWAITING_POINTS_REDEEM", "PICKUP_AWAITING_ADDRESS_BUTTON", "PICKUP_AWAITING_CONFIRMATION_ADDRESS"]:
        logger.info("[route_after_node] Response sent to user. Terminating graph execution run (END).")
        return END
    next_node = route_next_node(state)
    logger.info(f"[route_after_node] Response not sent yet. Routing immediately to next node: '{next_node}'")
    return next_node

# ----------------- COMPILE THE STATE GRAPH -----------------

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

# SQLite Checkpointer Configuration with WAL mode and Busy Timeout for Thread Safety
DB_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHECKPOINTS_DB = os.path.join(DB_DIR, "checkpoints.db")
conn = sqlite3.connect(CHECKPOINTS_DB, check_same_thread=False)
conn.execute("PRAGMA journal_mode=WAL;")
conn.execute("PRAGMA busy_timeout=5000;")
memory = SqliteSaver(conn)
compiled_graph = builder.compile(checkpointer=memory)
