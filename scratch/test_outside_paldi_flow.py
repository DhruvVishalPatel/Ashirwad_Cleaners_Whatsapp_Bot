import os
import sys

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.core.database import SessionLocal, init_db
from app.models.schemas import Customer, Order, OrderType
from app.services.crud import get_customer, create_customer
from app.core.graph import compiled_graph

def run_tests():
    init_db()

    phone_store_drop = "919999900001"
    phone_new_addr = "919999900002"
    phone_cancel = "919999900003"

    with SessionLocal() as db:
        # Clear any prior test customers
        for p in [phone_store_drop, phone_new_addr, phone_cancel]:
            c = db.query(Customer).filter(Customer.phone_number == p).first()
            if c:
                db.query(Order).filter(Order.customer_id == c.customer_id).delete()
                db.delete(c)
        db.commit()

    print("========================================")
    print("TEST 1: Store Drop-off Flow")
    print("========================================")
    with SessionLocal() as db:
        c1 = create_customer(db, phone_store_drop, name="Tester One", preferred_language="ENGLISH")
        c1_id = c1.customer_id

    config1 = {"configurable": {"thread_id": phone_store_drop}}

    # 1. Start Pickup
    state1 = {
        "phone_number": phone_store_drop,
        "customer_id": c1_id,
        "language": "ENGLISH",
        "current_flow": "PICKUP",
        "current_state": "PICKUP_AWAITING_ITEMS",
        "customer_name": "Tester One",
        "text_input": "2 shirts dry clean",
        "garments_list": [],
        "item_count": 0,
        "points_redeemed": 0,
        "saved_address": "",
        "pending_items_input": "",
        "direct_order_prefix": ""
    }
    res1 = compiled_graph.invoke(state1, config1)
    print("State after items:", res1.get("current_state"), "Base est:", res1.get("base_estimate"))
    assert res1.get("current_state") in ["PICKUP_AWAITING_CONFIRMATION_ADDRESS", "PICKUP_AWAITING_ADDRESS_BUTTON"]

    # 2. Provide address OUTSIDE Paldi
    res1["text_input"] = "101 Galaxy Heights, Bopal, Ahmedabad"
    res1 = compiled_graph.invoke(res1, config1)
    print("State after outside Paldi address:", res1.get("current_state"))
    assert res1.get("current_state") == "PICKUP_AWAITING_OUTSIDE_PALDI_CHOICE", f"Expected PICKUP_AWAITING_OUTSIDE_PALDI_CHOICE, got {res1.get('current_state')}"

    # 3. Select Store Drop
    res1["text_input"] = "btn_outside_store_drop"
    res1 = compiled_graph.invoke(res1, config1)
    print("State after selecting store drop:", res1.get("current_flow"), res1.get("current_state"))
    assert res1.get("current_flow") == "IDLE"
    assert res1.get("current_state") == ""

    with SessionLocal() as db:
        order = db.query(Order).filter(Order.customer_id == c1_id).first()
        assert order is not None, "Order should be created for store drop!"
        assert order.order_type == OrderType.STORE_DROP, f"Expected STORE_DROP, got {order.order_type}"
        assert order.delivery_fee == 0.0, f"Expected 0.0 delivery fee, got {order.delivery_fee}"
        assert "Raj Nagar complex" in order.flat_address
        print(f"PASSED Test 1: Order #{order.order_id} created with type {order.order_type.name} and address: {order.flat_address}")

    print("\n========================================")
    print("TEST 2: New Paldi Address Flow")
    print("========================================")
    with SessionLocal() as db:
        c2 = create_customer(db, phone_new_addr, name="Tester Two", preferred_language="ENGLISH")
        c2_id = c2.customer_id

    config2 = {"configurable": {"thread_id": phone_new_addr}}
    state2 = {
        "phone_number": phone_new_addr,
        "customer_id": c2_id,
        "language": "ENGLISH",
        "current_flow": "PICKUP",
        "current_state": "PICKUP_AWAITING_ITEMS",
        "customer_name": "Tester Two",
        "text_input": "1 pant dry clean",
        "garments_list": [],
        "item_count": 0,
        "points_redeemed": 0,
        "saved_address": "",
        "pending_items_input": "",
        "direct_order_prefix": ""
    }
    res2 = compiled_graph.invoke(state2, config2)
    
    # Send outside Paldi address
    res2["text_input"] = "Satellite, Ahmedabad"
    res2 = compiled_graph.invoke(res2, config2)
    assert res2.get("current_state") == "PICKUP_AWAITING_OUTSIDE_PALDI_CHOICE"

    # Select Paldi Address option
    res2["text_input"] = "btn_outside_paldi_addr"
    res2 = compiled_graph.invoke(res2, config2)
    print("State after clicking Paldi Address:", res2.get("current_state"))
    assert res2.get("current_state") == "PICKUP_AWAITING_CONFIRMATION_ADDRESS"

    # Now provide a valid Paldi address
    res2["text_input"] = "5 Swastik Society, Paldi, Ahmedabad"
    res2 = compiled_graph.invoke(res2, config2)
    print("State after providing Paldi address:", res2.get("current_flow"), res2.get("current_state"))
    assert res2.get("current_flow") == "IDLE"

    with SessionLocal() as db:
        order2 = db.query(Order).filter(Order.customer_id == c2_id).first()
        assert order2 is not None, "Order should be created for pickup!"
        assert order2.order_type == OrderType.PICKUP, f"Expected PICKUP, got {order2.order_type}"
        assert "Paldi" in order2.flat_address
        print(f"PASSED Test 2: Order #{order2.order_id} created with type {order2.order_type.name} and address: {order2.flat_address}")

    print("\n========================================")
    print("TEST 3: Cancel Order Flow")
    print("========================================")
    with SessionLocal() as db:
        c3 = create_customer(db, phone_cancel, name="Tester Three", preferred_language="ENGLISH")
        c3_id = c3.customer_id

    config3 = {"configurable": {"thread_id": phone_cancel}}
    state3 = {
        "phone_number": phone_cancel,
        "customer_id": c3_id,
        "language": "ENGLISH",
        "current_flow": "PICKUP",
        "current_state": "PICKUP_AWAITING_ITEMS",
        "customer_name": "Tester Three",
        "text_input": "3 shirts washing",
        "garments_list": [],
        "item_count": 0,
        "points_redeemed": 0,
        "saved_address": "",
        "pending_items_input": "",
        "direct_order_prefix": ""
    }
    res3 = compiled_graph.invoke(state3, config3)

    # Send outside Paldi address
    res3["text_input"] = "SG Highway, Ahmedabad"
    res3 = compiled_graph.invoke(res3, config3)
    assert res3.get("current_state") == "PICKUP_AWAITING_OUTSIDE_PALDI_CHOICE"

    # Select Cancel
    res3["text_input"] = "btn_outside_cancel"
    res3 = compiled_graph.invoke(res3, config3)
    print("State after cancelling:", res3.get("current_flow"), res3.get("current_state"))
    assert res3.get("current_flow") == "IDLE"
    assert res3.get("current_state") == ""

    with SessionLocal() as db:
        order3 = db.query(Order).filter(Order.customer_id == c3_id).first()
        assert order3 is None, "No order should be created when cancelled!"
        print("PASSED Test 3: Order gracefully cancelled, no order in DB.")

    print("\nALL 3 OUTSIDE-PALDI TESTS PASSED SUCCESSFULLY! 🎉")

if __name__ == "__main__":
    run_tests()
