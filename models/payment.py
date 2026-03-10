from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class PaymentStatus(str, Enum):
    pending = "pending"
    succeeded = "succeeded"
    canceled = "canceled"
    refunded = "refunded"


class PaymentCreate(BaseModel):
    user_id: int
    amount: Decimal = Field(gt=0)
    currency: str = Field(default="RUB", min_length=3, max_length=3)
    offer_type: str = Field(default="business_review", max_length=50)
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PaymentDB(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    yookassa_payment_id: Optional[str] = None
    amount: Decimal
    currency: str = "RUB"
    status: PaymentStatus = PaymentStatus.pending
    description: Optional[str] = None
    offer_type: str = "business_review"
    created_at: datetime
    paid_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
