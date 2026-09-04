from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.schemas import Customer
from app.services.crud import get_available_points

router = APIRouter(prefix="/customers", tags=["Customers"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class UpdateCustomerRequest(BaseModel):
    saved_address: Optional[str] = None
    last_location_gps: Optional[str] = None

@router.get("")
def list_customers(db: Session = Depends(get_db)):
    customers = db.query(Customer).all()
    result = []
    for c in customers:
        result.append({
            "customer_id": c.customer_id,
            "name": c.name or "Unknown",
            "phone_number": c.phone_number,
            "saved_address": c.saved_address or "",
            "last_location_gps": c.last_location_gps or "",
            "available_points": get_available_points(db, c.customer_id),
            "order_count": c.order_count
        })
    return result

@router.put("/{customer_id}")
def update_customer(customer_id: int, req: UpdateCustomerRequest, db: Session = Depends(get_db)):
    cust = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")

    if req.saved_address is not None:
        cust.saved_address = req.saved_address
    if req.last_location_gps is not None:
        cust.last_location_gps = req.last_location_gps

    db.commit()
    db.refresh(cust)

    return {
        "customer_id": cust.customer_id,
        "name": cust.name or "Unknown",
        "phone_number": cust.phone_number,
        "saved_address": cust.saved_address or "",
        "last_location_gps": cust.last_location_gps or "",
        "available_points": get_available_points(db, cust.customer_id),
        "order_count": cust.order_count
    }
