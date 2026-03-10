from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    user_id: int
    username: Optional[str] = Field(default=None, max_length=255)
    first_name: Optional[str] = Field(default=None, max_length=255)
    utm_source: Optional[str] = Field(default=None, max_length=100)
    referrer: Optional[str] = Field(default=None, max_length=255)


class UserUpdate(BaseModel):
    quest_state: Optional[str] = Field(default=None, max_length=50)
    quest_completed: Optional[bool] = None
    player_class: Optional[str] = Field(default=None, max_length=20)
    weapon: Optional[str] = Field(default=None, max_length=20)
    score: Optional[int] = Field(default=None, ge=0, le=3)
    round_number: Optional[int] = Field(default=None, ge=0, le=3)
    current_statement_hash: Optional[str] = Field(default=None, max_length=64)
    current_is_truth: Optional[bool] = None
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=255)
    workshop_registered: Optional[bool] = None
    arena_registered: Optional[bool] = None
    followup_stage: Optional[int] = None
    followup_completed: Optional[bool] = None
    is_blocked: Optional[bool] = None
    upsell_shown: Optional[bool] = None


class UserDB(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    quest_state: str = "start"
    quest_completed: bool = False
    player_class: Optional[str] = None
    weapon: Optional[str] = None
    score: int = 0
    round_number: int = 0
    current_statement_hash: Optional[str] = None
    current_is_truth: Optional[bool] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    workshop_registered: bool = False
    arena_registered: bool = False
    followup_stage: int = 0
    followup_completed: bool = False
    is_blocked: bool = False
    upsell_shown: bool = False
    created_at: datetime
    updated_at: datetime
    quest_completed_at: Optional[datetime] = None
    utm_source: Optional[str] = None
    referrer: Optional[str] = None
