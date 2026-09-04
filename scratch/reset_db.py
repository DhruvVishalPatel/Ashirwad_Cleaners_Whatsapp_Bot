import os
import sys
from dotenv import load_dotenv

sys.path.append("/Users/dhruvpatel/PROJECTS/Ashirwad_Cleaners_Bot")
load_dotenv("/Users/dhruvpatel/PROJECTS/Ashirwad_Cleaners_Bot/.env")

from app.core.database import engine, Base, init_db, SessionLocal
from app.models.schemas import Order, OrderItem, Customer, PointTransaction, Runner, CatalogItem

print("--- RESETTING DATABASE FOR FRESH START ---")

# 1. Drop all application tables and recreate
print("1. Dropping all tables in ashirwad.db...")
Base.metadata.drop_all(bind=engine)

print("2. Re-initializing schema & seeding price catalog...")
init_db()

# 3. Wipe LangGraph checkpoints SQLite DB if exists
checkpoints_db = os.path.join("/Users/dhruvpatel/PROJECTS/Ashirwad_Cleaners_Bot", "checkpoints.sqlite")
for ext in ["", "-wal", "-shm"]:
    fpath = checkpoints_db + ext
    if os.path.exists(fpath):
        try:
            os.remove(fpath)
            print(f"Removed checkpoint file: {fpath}")
        except Exception as e:
            print(f"Could not remove {fpath}: {e}")

with SessionLocal() as db:
    catalog_count = db.query(CatalogItem).count()
    cust_count = db.query(Customer).count()
    order_count = db.query(Order).count()
    print(f"\n✅ DATABASE RESET COMPLETE!")
    print(f"   Catalog Items (seeded): {catalog_count}")
    print(f"   Customers: {cust_count}")
    print(f"   Orders: {order_count}")
