from fastapi import APIRouter, HTTPException
from app.database.database import SessionLocal
from app.models.user import User
from app.auth.hashing import hash_password, verify_password
from app.auth.jwt_handler import create_access_token

router = APIRouter()

@router.post("/register")
def register(data: dict):
    db = SessionLocal()
    existing = db.query(User).filter(User.email == data["email"]).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        name=data["name"],
        email=data["email"],
        password=hash_password(data["password"]),
        role="employee",
    )
    db.add(user)
    db.commit()
    return {"message": "User Registered"}

@router.post("/login")
def login(data: dict):
    db = SessionLocal()
    user = db.query(User).filter(User.email == data["email"]).first()
    if not user or not verify_password(data["password"], user.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token({"email": user.email, "role": user.role})
    return {
        "access_token": token,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "id": user.id,
    }
