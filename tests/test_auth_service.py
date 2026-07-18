import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bson import ObjectId

from app.core.security import decode_access_token
from app.services.auth_service import DEMO_ACCOUNTS, AuthService


def test_exactly_ten_unique_demo_accounts_are_configured():
    assert len(DEMO_ACCOUNTS) == 10
    assert len({email for _, email in DEMO_ACCOUNTS}) == 10


def test_auth_service_seeds_and_authenticates_demo_accounts():
    user_id = ObjectId()
    collection = SimpleNamespace(
        update_one=AsyncMock(),
        find_one=AsyncMock(
            return_value={
                "_id": user_id,
                "email": DEMO_ACCOUNTS[0][1],
                "is_active": True,
                "is_demo": True,
            }
        ),
    )
    service = AuthService.__new__(AuthService)
    service._users = collection

    asyncio.run(service.ensure_demo_accounts())
    token = asyncio.run(service.login_demo_account(1))

    assert collection.update_one.await_count == 10
    collection.find_one.assert_awaited_once_with(
        {"email": DEMO_ACCOUNTS[0][1], "is_demo": True}
    )
    assert decode_access_token(token.access_token)["sub"] == str(user_id)


def test_auth_service_normalizes_email_and_full_name():
    assert AuthService._normalize_email(" USER@Example.COM ") == "user@example.com"
    assert AuthService._normalize_full_name("  Alice Example  ") == "Alice Example"
    assert AuthService._normalize_full_name("   ") is None


def test_auth_service_serializes_public_user_fields():
    user_id = ObjectId()
    user = AuthService._serialize_user(
        {
            "_id": user_id,
            "email": "USER@Example.COM",
            "full_name": "  Alice Example  ",
            "is_active": True,
        }
    )

    assert user.id == str(user_id)
    assert user.email == "user@example.com"
    assert user.full_name == "Alice Example"
    assert user.is_active is True

