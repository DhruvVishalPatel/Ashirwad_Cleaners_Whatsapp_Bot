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
        db.execute(text("ALTER TABLE customers ADD COLUMN bot_paused BOOLEAN DEFAULT 0"))
        db.commit()
    except Exception:
        db.rollback()

    try:
        db.execute(text("ALTER TABLE orders ADD COLUMN order_type VARCHAR(30) DEFAULT 'PICKUP_DELIVERY'"))
        db.commit()
    except Exception:
        db.rollback()

    try:
        db.execute(text("UPDATE customers SET preferred_language = 'ENGLISH' WHERE preferred_language IS NULL"))
        db.execute(text("UPDATE orders SET order_id = REPLACE(order_id, 'AC-', '') WHERE order_id LIKE 'AC-%'"))
        db.execute(text("UPDATE orders SET order_id = REPLACE(order_id, 'AC', '') WHERE order_id LIKE 'AC%'"))
        db.execute(text("UPDATE order_items SET order_id = REPLACE(order_id, 'AC-', '') WHERE order_id LIKE 'AC-%'"))
        db.execute(text("UPDATE order_items SET order_id = REPLACE(order_id, 'AC', '') WHERE order_id LIKE 'AC%'"))
        db.execute(text("UPDATE point_transactions SET order_id = REPLACE(order_id, 'AC-', '') WHERE order_id LIKE 'AC-%'"))
        db.execute(text("UPDATE point_transactions SET order_id = REPLACE(order_id, 'AC', '') WHERE order_id LIKE 'AC%'"))
        db.execute(text("UPDATE catalog_items SET service_type = 'petrol_wash' WHERE service_type = 'stain_removal'"))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

