import sys
from dotenv import load_dotenv

sys.path.append("/Users/dhruvpatel/PROJECTS/Ashirwad_Cleaners_Bot")
load_dotenv("/Users/dhruvpatel/PROJECTS/Ashirwad_Cleaners_Bot/.env")

from app.core.database import SessionLocal, init_db
from app.models.schemas import Customer
from app.services.crud import create_customer

print("--- TESTING CUSTOMER CREATION ---")
init_db()

phone = "919023654640"
with SessionLocal() as db:
    c = db.query(Customer).filter(Customer.phone_number == phone).first()
    if c:
        db.delete(c)
        db.commit()

with SessionLocal() as db:
    new_c = create_customer(db, phone_number=phone, name=None)
    print(f"Created customer ID: {new_c.customer_id}, preferred_language: {new_c.preferred_language}")
    assert new_c.preferred_language == "ENGLISH", "Expected preferred_language to default to 'ENGLISH'"

with SessionLocal() as db:
    c = db.query(Customer).filter(Customer.phone_number == phone).first()
    if c:
        db.delete(c)
        db.commit()

print("\n✅ CUSTOMER CREATION INTEGRITY TEST PASSED PERFECTLY!")
