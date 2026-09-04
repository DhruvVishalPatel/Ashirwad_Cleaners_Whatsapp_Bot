from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.schemas import Runner
from app.services.crud import get_runners, create_runner

router = APIRouter(prefix="/runners", tags=["Runners"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def format_wa_phone(phone: str) -> str:
    digits = "".join([c for c in phone if c.isdigit()])
    if len(digits) == 10:
        return f"91{digits}"
    if len(digits) == 12 and digits.startswith("91"):
        return digits
    return digits

class RunnerCreateRequest(BaseModel):
    name: str
    phone_number: str

class RunnerUpdateRequest(BaseModel):
    name: str
    phone_number: str

@router.get("")
def list_runners(db: Session = Depends(get_db)):
    runners = get_runners(db)
    return [
        {
            "runner_id": r.runner_id,
            "name": r.name,
            "phone_number": r.phone_number
        }
        for r in runners
    ]

@router.post("")
def add_runner(req: RunnerCreateRequest, db: Session = Depends(get_db)):
    if not req.name or not req.phone_number:
        raise HTTPException(status_code=400, detail="Name and phone_number are required")
    formatted_phone = format_wa_phone(req.phone_number)
    runner = create_runner(db, req.name, formatted_phone)
    return {
        "runner_id": runner.runner_id,
        "name": runner.name,
        "phone_number": runner.phone_number
    }

@router.put("/{runner_id}")
def update_runner(runner_id: int, req: RunnerUpdateRequest, db: Session = Depends(get_db)):
    runner = db.query(Runner).filter(Runner.runner_id == runner_id).first()
    if not runner:
        raise HTTPException(status_code=404, detail="Runner not found")
    formatted_phone = format_wa_phone(req.phone_number)
    runner.name = req.name
    runner.phone_number = formatted_phone
    db.commit()
    db.refresh(runner)
    return {
        "runner_id": runner.runner_id,
        "name": runner.name,
        "phone_number": runner.phone_number
    }

@router.delete("/{runner_id}")
def delete_runner(runner_id: int, db: Session = Depends(get_db)):
    runner = db.query(Runner).filter(Runner.runner_id == runner_id).first()
    if not runner:
        raise HTTPException(status_code=404, detail="Runner not found")
    db.delete(runner)
    db.commit()
    return {"message": "Runner deleted successfully"}
