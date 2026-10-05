import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.core.database import SessionLocal, init_db
from app.models.schemas import Customer, Order, OrderStatus, OrderType, OrderItem
from app.services.crud import create_customer, clean_order_id, now_ist
from app.core.graph import compiled_graph

def run_tests():
    init_db()

    phone_test = "919888800001"

    with SessionLocal() as db:
        c = db.query(Customer).filter(Customer.phone_number == phone_test).first()
        if c:
            db.query(OrderItem).filter(OrderItem.order_id.in_([o.order_id for o in c.orders])).delete(synchronize_session=False)
            db.query(Order).filter(Order.customer_id == c.customer_id).delete()
            db.delete(c)
        db.commit()

        cust = create_customer(db, phone_test, name="Dhruv Patel", preferred_language="ENGLISH")
        customer_id = cust.customer_id

    config = {"configurable": {"thread_id": phone_test}}

    def make_order(order_id: str, status: OrderStatus, item_count: int = 2):
        with SessionLocal() as db:
            o = Order(
                order_id=order_id,
                customer_id=customer_id,
                order_type=OrderType.PICKUP,
                status=status,
                item_count=item_count,
                estimated_amount=100.0,
                service_category="Dry Clean",
                flat_address="Paldi, Ahmedabad",
                created_at=now_ist()
            )
            db.add(o)
            db.commit()

    print("========================================")
    print("TEST 1: Single Active Order -> Confirmation -> Cancel")
    print("========================================")
    make_order("1029", OrderStatus.PENDING_PICKUP)

    state = {
        "phone_number": phone_test,
        "customer_id": customer_id,
        "language": "ENGLISH",
        "current_flow": "IDLE",
        "current_state": "",
        "customer_name": "Dhruv Patel",
        "text_input": "I want to cancel my order",
        "garments_list": [],
        "item_count": 0,
        "points_redeemed": 0,
        "saved_address": "",
        "pending_items_input": "",
        "direct_order_prefix": "",
        "cancel_order_id": ""
    }
    res = compiled_graph.invoke(state, config)
    print("Flow after cancel request:", res.get("current_flow"), "State:", res.get("current_state"), "Order to cancel:", res.get("cancel_order_id"))
    assert res.get("current_flow") == "CANCEL"
    assert res.get("current_state") == "CANCEL_AWAITING_CONFIRMATION"
    assert res.get("cancel_order_id") == "1029"

    # Confirm cancellation
    res["text_input"] = "btn_confirm_cancel_1029"
    res = compiled_graph.invoke(res, config)
    print("Flow after confirming cancel:", res.get("current_flow"), "State:", res.get("current_state"))
    assert res.get("current_flow") == "IDLE"

    with SessionLocal() as db:
        ord_1029 = db.query(Order).filter(Order.order_id == "1029").first()
        assert ord_1029.status == OrderStatus.CANCELLED, f"Expected CANCELLED, got {ord_1029.status}"
        print(f"PASSED Test 1: Order #1029 is now {ord_1029.status.name}")

    print("\n========================================")
    print("TEST 2: Keep Order (Abort cancellation)")
    print("========================================")
    make_order("1030", OrderStatus.PENDING_PICKUP)
    res["text_input"] = "Cancel 1030"
    res = compiled_graph.invoke(res, config)
    assert res.get("current_state") == "CANCEL_AWAITING_CONFIRMATION"

    # Say no / keep
    res["text_input"] = "btn_keep_order"
    res = compiled_graph.invoke(res, config)
    assert res.get("current_flow") == "IDLE"

    with SessionLocal() as db:
        ord_1030 = db.query(Order).filter(Order.order_id == "1030").first()
        assert ord_1030.status == OrderStatus.PENDING_PICKUP, f"Expected PENDING_PICKUP, got {ord_1030.status}"
        print(f"PASSED Test 2: Order #1030 remains {ord_1030.status.name}")

    print("\n========================================")
    print("TEST 3: Multiple Active Orders Selection")
    print("========================================")
    # Customer now has #1030 active, let's add #1031
    make_order("1031", OrderStatus.PENDING_PICKUP)

    res["text_input"] = "I want to cancel my order"
    res = compiled_graph.invoke(res, config)
    print("State with multiple orders:", res.get("current_flow"), res.get("current_state"))
    assert res.get("current_state") == "CANCEL_AWAITING_ORDER_SELECTION"

    # Select 1031 to cancel
    res["text_input"] = "1031"
    res = compiled_graph.invoke(res, config)
    assert res.get("current_state") == "CANCEL_AWAITING_CONFIRMATION"
    assert res.get("cancel_order_id") == "1031"

    # Confirm
    res["text_input"] = "yes cancel karo"
    res = compiled_graph.invoke(res, config)
    assert res.get("current_flow") == "IDLE"

    with SessionLocal() as db:
        ord_1031 = db.query(Order).filter(Order.order_id == "1031").first()
        assert ord_1031.status == OrderStatus.CANCELLED
        print(f"PASSED Test 3: Multiple orders prompt handled, Order #1031 is {ord_1031.status.name}")

    print("\n========================================")
    print("TEST 4: Disallow Cancel for IN_SHOP order")
    print("========================================")
    make_order("1032", OrderStatus.IN_SHOP)
    res["text_input"] = "Cancel 1032"
    res = compiled_graph.invoke(res, config)
    assert res.get("current_flow") == "IDLE"

    with SessionLocal() as db:
        ord_1032 = db.query(Order).filter(Order.order_id == "1032").first()
        assert ord_1032.status == OrderStatus.IN_SHOP
        print(f"PASSED Test 4: IN_SHOP order was rejected for cancellation, status is {ord_1032.status.name}")

    print("\nALL CANCELLATION TESTS PASSED SUCCESSFULLY! 🎉")

if __name__ == "__main__":
    run_tests()
