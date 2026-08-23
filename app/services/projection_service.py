from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import APP_TIMEZONE
from app.models import Insulin, MovementType, StockMovement
from app.services.stock_service import calculate_current_stock


def _to_local_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(APP_TIMEZONE)


def build_insulin_summary(
    db: Session,
    insulin: Insulin,
) -> dict:
    current_stock = calculate_current_stock(db, insulin.id)

    now_local = datetime.now(APP_TIMEZONE)
    today_local = now_local.date()
    lookback_date = today_local - timedelta(days=30)
    lookback_local = datetime.combine(
        lookback_date,
        time.min,
        tzinfo=APP_TIMEZONE,
    )
    lookback_utc = lookback_local.astimezone(timezone.utc)

    statement = (
        select(StockMovement)
        .where(
            StockMovement.insulin_id == insulin.id,
            StockMovement.movement_type == MovementType.DOSE,
            StockMovement.occurred_at >= lookback_utc,
        )
        .order_by(StockMovement.occurred_at)
    )

    dose_movements = db.scalars(statement).all()
    daily_consumption: dict[date, Decimal] = {}

    for movement in dose_movements:
        movement_date = _to_local_datetime(
            movement.occurred_at
        ).date()

        if movement_date >= today_local:
            continue

        used_units = abs(Decimal(movement.quantity_units))
        daily_consumption[movement_date] = (
            daily_consumption.get(
                movement_date,
                Decimal("0"),
            )
            + used_units
        )

    recorded_days = sorted(
        daily_consumption.keys(),
        reverse=True,
    )
    selected_days = recorded_days[:14]
    history_days_used = len(selected_days)

    if history_days_used < 3:
        return {
            "insulin_id": insulin.id,
            "insulin_name": insulin.name,
            "current_stock_units": current_stock,
            "average_daily_consumption_units": None,
            "history_days_used": history_days_used,
            "estimated_days_remaining": None,
            "estimated_end_date": None,
            "projection_available": False,
        }

    total_consumption = sum(
        (daily_consumption[day] for day in selected_days),
        Decimal("0"),
    )

    average_daily_consumption = (
        total_consumption / Decimal(history_days_used)
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    if average_daily_consumption <= 0 or current_stock <= 0:
        return {
            "insulin_id": insulin.id,
            "insulin_name": insulin.name,
            "current_stock_units": current_stock,
            "average_daily_consumption_units": average_daily_consumption,
            "history_days_used": history_days_used,
            "estimated_days_remaining": None,
            "estimated_end_date": None,
            "projection_available": False,
        }

    estimated_days = (
        current_stock / average_daily_consumption
    ).quantize(
        Decimal("0.1"),
        rounding=ROUND_HALF_UP,
    )

    estimated_end_date = today_local + timedelta(
        days=int(estimated_days)
    )

    return {
        "insulin_id": insulin.id,
        "insulin_name": insulin.name,
        "current_stock_units": current_stock,
        "average_daily_consumption_units": average_daily_consumption,
        "history_days_used": history_days_used,
        "estimated_days_remaining": estimated_days,
        "estimated_end_date": estimated_end_date,
        "projection_available": True,
    }
