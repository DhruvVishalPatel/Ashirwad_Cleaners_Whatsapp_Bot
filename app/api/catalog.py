from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.schemas import CatalogItem

router = APIRouter(prefix="/catalog", tags=["Catalog"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class CatalogItemCreateRequest(BaseModel):
    service_type: str
    item_name: str
    price: float
    is_variable: Optional[bool] = False
    note: Optional[str] = None

class CatalogItemUpdateRequest(BaseModel):
    item_name: str
    price: float
    is_variable: Optional[bool] = False
    note: Optional[str] = None

@router.get("")
def list_catalog(service_type: Optional[str] = Query(None), db: Session = Depends(get_db)):
    query = db.query(CatalogItem)
    if service_type:
        query = query.filter(CatalogItem.service_type == service_type)
    items = query.all()
    return [
        {
            "id": item.id,
            "service_type": item.service_type,
            "item_name": item.item_name,
            "price": item.price,
            "is_variable": item.is_variable,
            "note": item.note or ""
        }
        for item in items
    ]

@router.post("")
def create_catalog_item(req: CatalogItemCreateRequest, db: Session = Depends(get_db)):
    if not req.item_name or not req.service_type:
        raise HTTPException(status_code=400, detail="service_type and item_name are required")
    
    item = CatalogItem(
        service_type=req.service_type,
        item_name=req.item_name.strip(),
        price=req.price,
        is_variable=req.is_variable or False,
        note=req.note.strip() if req.note else None
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    return {
        "id": item.id,
        "service_type": item.service_type,
        "item_name": item.item_name,
        "price": item.price,
        "is_variable": item.is_variable,
        "note": item.note or ""
    }

@router.put("/{item_id}")
def update_catalog_item(item_id: int, req: CatalogItemUpdateRequest, db: Session = Depends(get_db)):
    item = db.query(CatalogItem).filter(CatalogItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Catalog item not found")

    item.item_name = req.item_name
    item.price = req.price
    item.is_variable = req.is_variable
    item.note = req.note

    db.commit()
    db.refresh(item)

    return {
        "id": item.id,
        "service_type": item.service_type,
        "item_name": item.item_name,
        "price": item.price,
        "is_variable": item.is_variable,
        "note": item.note or ""
    }

@router.delete("/{item_id}")
def delete_catalog_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(CatalogItem).filter(CatalogItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Catalog item not found")

    db.delete(item)
    db.commit()
    return {"message": "Catalog item deleted successfully"}
