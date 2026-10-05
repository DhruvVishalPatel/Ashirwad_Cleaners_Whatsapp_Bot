from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_status_update():
    # 1. Create a dummy order or fetch existing order
    orders_res = client.get("/api/v1/orders?show_all=true")
    orders = orders_res.json()
    print("Orders count:", len(orders))
    
    if orders:
        order_id = orders[0]["order_id"]
        print(f"Testing status update for Order #{order_id}...")
        
        # Test updating price first
        price_res = client.put(f"/api/v1/orders/{order_id}/price", json={"raw_price": 100.0})
        print("Price update status:", price_res.status_code, price_res.text)

        # Test updating status to IN_SHOP
        status_res = client.put(f"/api/v1/orders/{order_id}/status", json={"status": "IN_SHOP", "payment_status": "PENDING"})
        print("Status update response:", status_res.status_code, status_res.text)

if __name__ == "__main__":
    test_status_update()
