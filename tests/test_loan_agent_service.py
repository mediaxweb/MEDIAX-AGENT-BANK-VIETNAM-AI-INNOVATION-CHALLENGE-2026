import asyncio
from types import SimpleNamespace

import pytest
from bson import ObjectId

from app.api.schemas.loan_agent import CustomerCreateRequest, LoanLimitCalculationRequest
from app.services.loan_agent_service import LoanAgentService, LoanAgentValidationError


class FakeCollection:
    def __init__(self, found=None):
        self.found = found
        self.inserted = []

    async def find_one(self, query):
        return self.found

    async def insert_one(self, document):
        self.inserted.append(document.copy())
        return SimpleNamespace(inserted_id=ObjectId())


class FakeDatabase:
    def __init__(self, collections):
        self.collections = collections

    def get_loan_collection(self, name):
        return self.collections[name]


def test_create_customer_rejects_duplicate_identity_before_insert():
    customers = FakeCollection(found={"_id": ObjectId(), "national_id": "001"})
    service = LoanAgentService(FakeDatabase({"loan_customers": customers}))

    with pytest.raises(LoanAgentValidationError, match="same identity"):
        asyncio.run(
            service.create_customer(
                user_id="loan-user",
                payload=CustomerCreateRequest(full_name="Demo", national_id="001"),
            )
        )

    assert customers.inserted == []


def test_persisted_limit_is_zero_when_case_has_hard_stop():
    profile_id = ObjectId()
    profiles = FakeCollection(
        found={
            "_id": profile_id,
            "user_id": "loan-user",
            "loan_amount": 8_000_000_000,
            "currency": "VND",
        }
    )
    calculations = FakeCollection()
    service = LoanAgentService(
        FakeDatabase(
            {
                "loan_profiles": profiles,
                "loan_limit_calculations": calculations,
            }
        )
    )

    result = asyncio.run(
        service.calculate_loan_limit(
            user_id="loan-user",
            loan_profile_id=str(profile_id),
            payload=LoanLimitCalculationRequest(
                total_capital_need=10_000_000_000,
                collateral_value=10_000_000_000,
                ltv_ratio=0.8,
                dscr=1.35,
                checklist_score=94,
                hard_stop=True,
            ),
        )
    )

    assert result.calculated_limit == 8_000_000_000
    assert result.final_factor == 0
    assert result.recommended_limit == 0
