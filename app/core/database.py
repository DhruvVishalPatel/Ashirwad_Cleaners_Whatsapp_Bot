from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.schemas import Base
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'ashirwad.db')}")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)
    
    # Safe migration: Add preferred_language, picked_up_at, delivered_at if they don't exist
    from sqlalchemy import text
    db = SessionLocal()
    try:
        db.execute(text("ALTER TABLE customers ADD COLUMN preferred_language VARCHAR DEFAULT 'ENGLISH'"))
        db.commit()
    except Exception:
        db.rollback()
        
    try:
        db.execute(text("ALTER TABLE orders ADD COLUMN picked_up_at DATETIME"))
        db.commit()
    except Exception:
        db.rollback()

    try:
        db.execute(text("ALTER TABLE orders ADD COLUMN delivered_at DATETIME"))
        db.commit()
    except Exception:
        db.rollback()

    try:
        db.execute(text("UPDATE orders SET order_id = REPLACE(order_id, 'AC-', '') WHERE order_id LIKE 'AC-%'"))
        db.execute(text("UPDATE orders SET order_id = REPLACE(order_id, 'AC', '') WHERE order_id LIKE 'AC%'"))
        db.execute(text("UPDATE order_items SET order_id = REPLACE(order_id, 'AC-', '') WHERE order_id LIKE 'AC-%'"))
        db.execute(text("UPDATE order_items SET order_id = REPLACE(order_id, 'AC', '') WHERE order_id LIKE 'AC%'"))
        db.execute(text("UPDATE point_transactions SET order_id = REPLACE(order_id, 'AC-', '') WHERE order_id LIKE 'AC-%'"))
        db.execute(text("UPDATE point_transactions SET order_id = REPLACE(order_id, 'AC', '') WHERE order_id LIKE 'AC%'"))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

    # Seed the price catalog if it is empty
    from app.models.schemas import CatalogItem
    import json
    db = SessionLocal()
    try:
        if db.query(CatalogItem).count() == 0:
            print("Seeding CatalogItem table from price_list.json...")
            price_list_path = os.path.join(BASE_DIR, "price_list.json")
            if os.path.exists(price_list_path):
                with open(price_list_path, "r") as f:
                    data = json.load(f)
                services = data.get("services", {})
                for service_type, service_data in services.items():
                    items = service_data.get("items", [])
                    for item in items:
                        db_item = CatalogItem(
                            service_type=service_type,
                            item_name=item["item_name"],
                            price=item["base_price"],
                            is_variable=item.get("is_variable", False),
                            note=item.get("note", None)
                        )
                        db.add(db_item)
                db.commit()
                print("Seeding complete!")
            else:
                print("Warning: price_list.json not found, skipping seed.")
    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

