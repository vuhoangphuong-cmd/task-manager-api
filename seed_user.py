import argparse

from app.db import Base, SessionLocal, engine
from app.models import User
from app.security import get_password_hash


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--full-name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", choices=["manager", "staff"], required=True)
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        existing = db.query(User).filter(
            (User.username == args.username) | (User.email == args.email)
        ).first()
        if existing:
            print("User đã tồn tại, không tạo mới.")
            return

        user = User(
            username=args.username,
            full_name=args.full_name,
            email=args.email,
            role=args.role,
            hashed_password=get_password_hash(args.password),
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"Đã tạo user: {user.username} ({user.role})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
