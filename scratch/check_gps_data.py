from app.core.database import SessionLocal
from app.models.schemas import Customer

with SessionLocal() as db:
    customers = db.query(Customer).filter(Customer.last_location_gps.isnot(None)).all()
    print(f"Found {len(customers)} customers with GPS data:")
    for c in customers:
        print(f"ID: {c.customer_id} | Name: {c.name} | Phone: {c.phone_number} | GPS: '{c.last_location_gps}'")
