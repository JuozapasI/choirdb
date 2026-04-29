# create_admin.py
from getpass import getpass
from app import database, models, auth
from sqlalchemy.orm import Session

def main():
    username = input("Enter admin username: ")
    password = getpass("Enter admin password: ")
    confirm = getpass("Confirm password: ")

    if password != confirm:
        print("Passwords do not match!")
        return

    db: Session = next(database.get_db())

    # Check if user already exists
    existing = db.query(models.User).filter(models.User.username == username).first()
    if existing:
        print("User already exists!")
        db.close()
        return

    hashed_pw = auth.get_password_hash(password)
    admin_user = models.User(username=username, hashed_password=hashed_pw, role=models.UserRole.ADMIN, is_verified=True)

    db.add(admin_user)
    db.commit()
    db.close()
    print(f"Admin user '{username}' created successfully.")

if __name__ == "__main__":
    main()
