"""Import or update local operator accounts from the documented users.txt format."""
import argparse
from pathlib import Path

from sqlalchemy import or_

from app.core.security import hash_password
from app.db.database import Base, SessionLocal, engine
from app.db.models import User

FIELDS = {
    "Full name": "full_name",
    "Email": "email",
    "Password": "password",
    "Role": "role",
}
ALLOWED_ROLES = {"admin", "security", "user"}


def parse_users(path: Path) -> list[dict]:
    records, current = [], {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        field = next((label for label in FIELDS if line.startswith(label + ":")), None)
        if not field:
            continue
        if field == "Full name" and current:
            records.append(current)
            current = {}
        value = line.split(":", 1)[1].strip()
        if not value:
            raise ValueError(f"Empty {field!r} at line {line_number}")
        current[FIELDS[field]] = value
    if current:
        records.append(current)

    required = set(FIELDS.values())
    for index, record in enumerate(records, 1):
        missing = required - record.keys()
        if missing:
            raise ValueError(f"User {index} is missing: {', '.join(sorted(missing))}")
        record["email"] = record["email"].lower()
        record["username"] = record["email"].split("@", 1)[0]
        if "@" not in record["email"]:
            raise ValueError(f"Invalid email for user {index}")
        if record["role"] not in ALLOWED_ROLES:
            raise ValueError(f"Invalid role for {record['email']}: {record['role']}")
        if not 8 <= len(record["password"]) <= 128:
            raise ValueError(f"Password for {record['email']} must contain 8 to 128 characters")
    if not records:
        raise ValueError("No users were found")
    return records


def import_users(db, records: list[dict]) -> tuple[int, int]:
    created = updated = 0
    try:
        for record in records:
            matches = db.query(User).filter(or_(
                User.email == record["email"], User.username == record["username"]
            )).all()
            if len(matches) > 1:
                raise ValueError(f"Email and username belong to different accounts: {record['email']}")
            user = matches[0] if matches else None
            if user is None:
                user = User(email=record["email"], username=record["username"])
                db.add(user)
                created += 1
            else:
                updated += 1
            user.full_name = record["full_name"]
            user.role = record["role"]
            user.is_active = True
            user.hashed_password = hash_password(record["password"])
        db.commit()
    except Exception:
        db.rollback()
        raise
    return created, updated


def main():
    parser = argparse.ArgumentParser(description="Import users from users.txt")
    parser.add_argument("path", nargs="?", default="users.txt", type=Path)
    args = parser.parse_args()
    if not args.path.is_file():
        parser.error(f"File not found: {args.path}")
    records = parse_users(args.path)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        created, updated = import_users(db, records)
    print(f"Import complete: {created} created, {updated} updated, {len(records)} total")


if __name__ == "__main__":
    main()
