import os
import hashlib
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["Auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    token: str
    username: str

def get_expected_token() -> str:
    env_user = os.getenv("ADMIN_USERNAME", "admin")
    env_pass = os.getenv("ADMIN_PASSWORD", "ashirwad123")
    return hashlib.sha256(f"{env_user}:{env_pass}".encode()).hexdigest()

@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest):
    env_user = os.getenv("ADMIN_USERNAME", "admin")
    env_pass = os.getenv("ADMIN_PASSWORD", "ashirwad123")
    
    if req.username == env_user and req.password == env_pass:
        token = get_expected_token()
        return LoginResponse(token=token, username=req.username)
    
    raise HTTPException(status_code=401, detail="Invalid username or password")

@router.get("/verify")
def verify(token: str):
    expected = get_expected_token()
    if token == expected:
        return {"valid": True}
    return {"valid": False}
