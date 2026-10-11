import os
import sys

# Ensure root path is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, ".env"))

from app.core.database import SessionLocal, init_db
from app.models.schemas import OrderItem, Order, ChatMessage, PointTransaction, Customer, Runner, CatalogItem

def clear_test_data():
    print("=" * 60)
    print("🚀 ASHIRWAD CLEANERS - PRODUCTION LAUNCH DATABASE RESET")
    print("=" * 60)
    print("Clearing test customers, staff, orders, and bot chat logs...")
    print("Preserving price catalog...\n")

    with SessionLocal() as db:
        # Delete dependent tables in order of foreign key constraints
        items_deleted = db.query(OrderItem).delete()
        orders_deleted = db.query(Order).delete()
        messages_deleted = db.query(ChatMessage).delete()
        points_deleted = db.query(PointTransaction).delete()
        customers_deleted = db.query(Customer).delete()
        runners_deleted = db.query(Runner).delete()
        
        db.commit()

        # Check and ensure catalog items are preserved
        catalog_count = db.query(CatalogItem).count()
        if catalog_count == 0:
            print("Catalog table was empty. Re-seeding from price_list.json...")
            init_db()
            catalog_count = db.query(CatalogItem).count()

        print("✅ DATABASE CLEANUP SUMMARY:")
        print(f"   • Order Items Deleted:        {items_deleted}")
        print(f"   • Orders Deleted:             {orders_deleted}")
        print(f"   • Chat Messages Deleted:      {messages_deleted}")
        print(f"   • Point Transactions Deleted: {points_deleted}")
        print(f"   • Customers Deleted:          {customers_deleted}")
        print(f"   • Staff / Runners Deleted:    {runners_deleted}")
        print(f"   • Price Catalog Preserved:    {catalog_count} items intact! ✨\n")

    # Wipe LangGraph SQLite conversational checkpoint database so bot memory is brand new
    checkpoint_bases = ["checkpoints.db", "checkpoints.sqlite"]
    for base_name in checkpoint_bases:
        for ext in ["", "-wal", "-shm"]:
            fpath = os.path.join(BASE_DIR, base_name + ext)
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                    print(f"   • Wiped bot state file: {base_name + ext}")
                except Exception as e:
                    print(f"   • Notice: could not remove {base_name + ext} ({e})")

    # Re-initialize clean DB schema
    init_db()
    print("\n🎉 All test data cleared! Ashirwad Cleaners is completely fresh for real customers.")

if __name__ == "__main__":
    clear_test_data()
