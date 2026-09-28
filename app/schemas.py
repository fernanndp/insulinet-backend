from datetime import date, datetime, time
from decimal import Decimal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
)


class InsulinCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=100,
    )

    concentration_units_per_ml: Decimal = Field(
        gt=0
    )

    container_volume_ml: Decimal = Field(
        gt=0
    )

    open_validity_days: int = Field(
        default=28,
        ge=1,
        le=180,
    )


class InsulinResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: int
    name: str

    concentration_units_per_ml: Decimal
    container_volume_ml: Decimal
    open_validity_days: int

    active: bool
    created_at: datetime


class InsulinUpdate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=100,
    )

    concentration_units_per_ml: Decimal = Field(
        gt=0
    )

    container_volume_ml: Decimal = Field(
        gt=0
    )

    open_validity_days: int = Field(
        ge=1,
        le=180,
    )

    active: bool


class StockInCreate(BaseModel):
    containers: int = Field(
        gt=0
    )

    expiration_date: date | None = None


class StockMovementResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: int
    insulin_id: int
    container_id: int
    group_id: int | None

    movement_type: str
    quantity_units: Decimal

    expiration_date: date | None

    occurred_at: datetime
    occurred_time_known: bool

    notes: str | None
    created_at: datetime


class StockSummaryResponse(BaseModel):
    insulin_id: int
    insulin_name: str
    current_stock_units: Decimal


class StockInUpdate(BaseModel):
    units: Decimal = Field(
        gt=0
    )

    expiration_date: date | None = None


class StockAdjustmentCreate(BaseModel):
    actual_stock_units: Decimal = Field(
        ge=0
    )

    notes: str = Field(
        min_length=3,
        max_length=500,
    )


class ContainerExpirationUpdate(BaseModel):
    container_ids: list[int] = Field(
        min_length=1
    )

    expiration_date: date


class InsulinContainerResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: int
    insulin_id: int

    status: str

    initial_units: Decimal
    remaining_units: Decimal

    opened_at: datetime | None
    created_at: datetime

    expires_at: datetime | None

    days_until_expiration: int | None

    expiration_status: str

    expiration_source: str | None

    stock_expiration_date: date | None

    open_discard_date: date | None


class DoseCreate(BaseModel):
    units: Decimal = Field(
        gt=0
    )

    occurred_date: date | None = None

    occurred_time: time | None = None

    notes: str | None = Field(
        default=None,
        max_length=500,
    )


class DoseUpdate(BaseModel):
    units: Decimal = Field(
        gt=0
    )

    occurred_date: date

    occurred_time: time | None = None

    notes: str | None = Field(
        default=None,
        max_length=500,
    )


class DoseBatchItem(BaseModel):
    occurred_date: date

    units: Decimal = Field(
        gt=0
    )

    occurred_time: time | None = None

    notes: str | None = Field(
        default=None,
        max_length=500,
    )


class DoseBatchCreate(BaseModel):
    doses: list[DoseBatchItem] = Field(
        min_length=1
    )


class StockHistoryItem(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: int
    container_id: int
    group_id: int | None

    movement_type: str
    quantity_units: Decimal

    expiration_date: date | None

    occurred_at: datetime
    occurred_time_known: bool

    notes: str | None


class InsulinSummaryResponse(BaseModel):
    insulin_id: int
    insulin_name: str

    current_stock_units: Decimal

    average_daily_consumption_units: Decimal | None
    history_days_used: int

    estimated_days_remaining: Decimal | None
    estimated_end_date: date | None

    projection_available: bool

    stock_alert_level: str

    container_alert_level: str
    container_alert_days: int | None

    next_expiration_date: date | None
    days_until_expiration: int | None
    expiring_stock_units: Decimal | None

    estimated_expiring_stock_end_date: (
        date | None
    )

    expiration_status: str


class UserCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=100,
    )

    email: EmailStr

    password: str = Field(
        min_length=1,
        max_length=128,
    )


class UserResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: int
    name: str
    email: EmailStr
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    message: str


class ResetPasswordRequest(BaseModel):
    token: str = Field(
        min_length=20,
        max_length=500,
    )

    new_password: str = Field(
        min_length=1,
        max_length=128,
    )


class ResetPasswordResponse(BaseModel):
    message: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(
        min_length=1,
        max_length=128,
    )

    new_password: str = Field(
        min_length=1,
        max_length=128,
    )


class ChangePasswordResponse(BaseModel):
    message: str