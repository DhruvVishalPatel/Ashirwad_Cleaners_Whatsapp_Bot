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
    # Safe migration: Add preferred_language if it doesn't exist
    from sqlalchemy import text
    db = SessionLocal()
    try:
        db.execute(text("ALTER TABLE customers ADD COLUMN preferred_language VARCHAR DEFAULT 'ENGLISH'"))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

