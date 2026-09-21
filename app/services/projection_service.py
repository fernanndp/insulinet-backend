from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import APP_TIMEZONE
from app.models import ContainerStatus, Insulin, MovementType, StockMovement
from app.services.container_service import (
    compute_container_expiration,
    list_containers,
)
from app.services.stock_service import calculate_current_stock

LOW_STOCK_WARNING_DAYS = Decimal("7")
LOW_STOCK_CRITICAL_DAYS = Decimal("3")

LOW_STOCK_WARNING_FRACTION = Decimal("0.40")
LOW_STOCK_CRITICAL_FRACTION = Decimal("0.20")


def _to_local_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(APP_TIMEZONE)


def _compute_stock_alert_level(
    current_stock: Decimal,
    estimated_days_remaining: Decimal | None,
    container_units: Decimal,
) -> str:
    if current_stock <= 0:
        return "critical"

    if estimated_days_remaining is not None:
        if estimated_days_remaining <= LOW_STOCK_CRITICAL_DAYS:
            return "critical"

        if estimated_days_remaining <= LOW_STOCK_WARNING_DAYS:
            return "low"

        return "ok"

    # No consumption history yet: fall back to how much of a single
    # container/pen is left, so a near-empty stock is still flagged
    # even before there is enough data to estimate days remaining.
    if container_units > 0:
        remaining_fraction = current_stock / container_units

        if remaining_fraction <= LOW_STOCK_CRITICAL_FRACTION:
            return "critical"

        if remaining_fraction <= LOW_STOCK_WARNING_FRACTION:
            return "low"

    return "unknown"


def _compute_container_alert(
    db: Session,
    insulin: Insulin,
    today_local: date,
) -> tuple[str, int | None]:
    open_containers = [
        container
        for container in list_containers(db, insulin.id)
        if container.status == ContainerStatus.OPEN
    ]

    alert_level = "ok"
    alert_days: int | None = None

    for container in open_containers:
        expiration = compute_container_expiration(
            container,
            insulin.open_validity_days,
            today_local,
        )
        status = expiration["expiration_status"]
        days = expiration["days_until_expiration"]

        if status == "expired":
            if alert_level != "expired":
                alert_level = "expired"
                alert_days = days
            elif days is not None and (
                alert_days is None or days < alert_days
            ):
                alert_days = days
        elif status == "expiring_soon" and alert_level == "ok":
            alert_level = "expiring_soon"
            alert_days = days

    return alert_level, alert_days


def build_insulin_summary(
    db: Session,
    insulin: Insulin,
) -> dict:
    current_stock = calculate_current_stock(db, insulin.id)
    container_units = (
        insulin.concentration_units_per_ml
        * insulin.container_volume_ml
    )

    now_local = datetime.now(APP_TIMEZONE)
    today_local = now_local.date()

    container_alert_level, container_alert_days = (
        _compute_container_alert(db, insulin, today_local)
    )

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
            "stock_alert_level": _compute_stock_alert_level(
                current_stock, None, container_units
            ),
            "container_alert_level": container_alert_level,
            "container_alert_days": container_alert_days,
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
            "stock_alert_level": _compute_stock_alert_level(
                current_stock, None, container_units
            ),
            "container_alert_level": container_alert_level,
            "container_alert_days": container_alert_days,
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
        "stock_alert_level": _compute_stock_alert_level(
            current_stock, estimated_days, container_units
        ),
        "container_alert_level": container_alert_level,
        "container_alert_days": container_alert_days,
    }
