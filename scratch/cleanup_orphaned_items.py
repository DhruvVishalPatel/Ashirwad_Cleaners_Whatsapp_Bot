from app.core.database import SessionLocal
from app.models.schemas import Order, OrderItem

def cleanup_database():
    db = SessionLocal()
    try:
        # Fetch all active order IDs
        active_order_ids = [o.order_id for o in db.query(Order).all()]
        
        # Query items whose order_id does not belong to any active order
        orphaned_items = db.query(OrderItem).filter(~OrderItem.order_id.in_(active_order_ids)).all()
        
        print("--- DATABASE ORPHAN CLEANUP START ---")
        print(f"Found {len(orphaned_items)} orphaned garment item records.")
        
        for item in orphaned_items:
            print(f"🗑️ Deleting orphaned item: ID={item.id}, Order ID={item.order_id}, {item.quantity}x {item.garment_type} ({item.service_type})")
            db.delete(item)
            
        db.commit()
        print("Database cleanup completed successfully!")
        print("--- DATABASE ORPHAN CLEANUP END ---")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error during database cleanup: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_database()
