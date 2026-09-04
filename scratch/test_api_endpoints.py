import os
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_api():
    print("Testing /api/v1/auth/login...")
    login_res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "ashirwad123"})
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["token"]
    print("Token received:", token)

    print("Testing /api/v1/orders/analytics...")
    analytics_res = client.get("/api/v1/orders/analytics")
    assert analytics_res.status_code == 200
    print("Analytics data:", analytics_res.json())

    print("Testing /api/v1/orders...")
    orders_res = client.get("/api/v1/orders")
    assert orders_res.status_code == 200
    orders = orders_res.json()
    print(f"Retrieved {len(orders)} active orders.")

    print("Testing /api/v1/customers...")
    cust_res = client.get("/api/v1/customers")
    assert cust_res.status_code == 200
    print(f"Retrieved {len(cust_res.json())} customers.")

    print("Testing /api/v1/runners...")
    runners_res = client.get("/api/v1/runners")
    assert runners_res.status_code == 200
    print(f"Retrieved {len(runners_res.json())} runners.")

    print("Testing /api/v1/catalog...")
    cat_res = client.get("/api/v1/catalog")
    assert cat_res.status_code == 200
    print(f"Retrieved {len(cat_res.json())} catalog items.")

    print("ALL API VERIFICATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_api()
