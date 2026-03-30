from app.db import Base, SessionLocal, engine
from app.models import User
from app.security import get_password_hash

Base.metadata.create_all(bind=engine)

db = SessionLocal()
try:
    seed_data = [
        {
            "username": "manager01",
            "password": "Manager@123",
            "full_name": "Manager Demo",
            "email": "manager01@example.com",
            "role": "manager",
        },
        {
            "username": "staff01",
            "password": "Staff@123",
            "full_name": "Staff Demo",
            "email": "staff01@example.com",
            "role": "staff",
        },
    ]

    for item in seed_data:
        existing = db.query(User).filter(User.username == item["username"]).first()
        if existing:
            print(f"DA TON TAI: {item['username']}")
            continue

        user = User(
            username=item["username"],
            full_name=item["full_name"],
            email=item["email"],
            role=item["role"],
            hashed_password=get_password_hash(item["password"]),
            is_active=True,
        )
        db.add(user)

    db.commit()
    print("DA TAO USER XONG")
finally:
    db.close()
