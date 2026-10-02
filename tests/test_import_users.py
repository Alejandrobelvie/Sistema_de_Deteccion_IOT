from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.db.import_users import import_users, parse_users
from app.db.models import User


def test_parse_and_idempotent_import(tmp_path: Path):
    source = tmp_path / "users.txt"
    source.write_text("""Header

Full name: Admin Person
Email: ADMIN@example.com
Password: password123
Role: admin

Full name: Worker Person
Email: worker@example.com
Password: password456
Role: user

Instructions that must be ignored.
""", encoding="utf-8")
    records = parse_users(source)
    assert [record["username"] for record in records] == ["admin", "worker"]

    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        assert import_users(db, records) == (2, 0)
        records[1]["role"] = "security"
        assert import_users(db, records) == (0, 2)
        assert db.query(User).count() == 2
        assert db.query(User).filter_by(username="worker").one().role == "security"
    engine.dispose()


def test_parse_rejects_incomplete_or_invalid_account(tmp_path: Path):
    source = tmp_path / "users.txt"
    source.write_text("Full name: Missing fields\nEmail: invalid\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing"):
        parse_users(source)
