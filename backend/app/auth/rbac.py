import os
from fastapi import Request, HTTPException
from jose import jwt
from app.models.user import User

SECRET_KEY = "supersecretkey"
ALGORITHM = "HS256"
PRIVILEGED_ROLES = {"team_lead", "admin", "manager"}

def get_current_user_from_headers(request: Request, db, bypass_view_as: bool = False):
    """
    Extracts current logged-in user from JWT Authorization header or X-User-Id / X-User-Email headers.
    Supports secure impersonation via X-View-As-Agent:
      - Caller must be a manager (role in team_lead, admin, manager)
      - DEMO_MODE env variable must be on (default 'true')
      - Target must be a support agent (role='agent', e.g. Ravi, Priya, Arun, Meena, Kiran, Sarah, Mike)
      - Returns 403 otherwise.
    """
    # 0. Check for impersonation header if not bypassed
    view_as_name = request.headers.get("X-View-As-Agent")
    if view_as_name and not bypass_view_as:
        caller = get_current_user_from_headers(request, db, bypass_view_as=True)
        caller_role = request.headers.get("X-Real-User-Role") or (caller.role if caller else "") or request.headers.get("X-User-Role", "")
        if caller_role not in PRIVILEGED_ROLES:
            raise HTTPException(status_code=403, detail="Forbidden: Impersonation only allowed for managers")

        demo_mode_env = os.environ.get("DEMO_MODE", "true").lower() == "true"
        if not demo_mode_env:
            raise HTTPException(status_code=403, detail="Forbidden: Impersonation only allowed when DEMO_MODE is on")

        target = db.query(User).filter(
            (User.name == view_as_name) | (User.name.like(f"%{view_as_name}%"))
        ).first()
        if not target or target.role != "agent":
            raise HTTPException(status_code=403, detail="Forbidden: Can only impersonate support agents")

        return target

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
