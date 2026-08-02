from app.database.database import SessionLocal
from app.models.user import User
from app.auth.hashing import hash_password

db = SessionLocal()

existing = db.query(User).filter(User.email == "admin@smartdesk.com").first()
if existing:
    print("User already exists:")
    print(f"  Email : admin@smartdesk.com")
    print(f"  Pass  : admin123")
else:
    user = User(
        name="Admin User",
        email="admin@smartdesk.com",
        password=hash_password("admin123"),
        role="admin",
    )
    db.add(user)
    db.commit()
    print("User created successfully:")
    print(f"  Email : admin@smartdesk.com")
    print(f"  Pass  : admin123")
