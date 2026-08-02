from fastapi import Request, HTTPException
from jose import jwt
from app.models.user import User

SECRET_KEY = "supersecretkey"
ALGORITHM = "HS256"

def get_current_user_from_headers(request: Request, db):
    """
    Extracts current logged-in user from JWT Authorization header or X-User-Id / X-User-Email headers.
    """
    # 1. Check Authorization Bearer token
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            email = payload.get("email")
            if email:
                user = db.query(User).filter(User.email == email).first()
                if user:
                    return user
        except Exception:
            pass

    # 2. Check X-User-Id / X-User-Email headers
    user_id = request.headers.get("X-User-Id")
    if user_id:
        try:
            user = db.query(User).filter(User.id == int(user_id)).first()
            if user:
                return user
        except Exception:
            pass

    user_email = request.headers.get("X-User-Email")
    if user_email:
        user = db.query(User).filter(User.email == user_email).first()
        if user:
            return user

    return None
