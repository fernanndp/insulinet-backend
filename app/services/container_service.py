from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import APP_TIMEZONE
from app.models import ContainerStatus, InsulinContainer, StockMovement

OPEN_EXPIRATION_WARNING_DAYS = 5


def list_containers(
    db: Session,
    insulin_id: int,
) -> list[InsulinContainer]:
    statement = (
        select(InsulinContainer)
        .where(InsulinContainer.insulin_id == insulin_id)
        .order_by(
            InsulinContainer.created_at,
            InsulinContainer.id,
        )
    )
    return list(db.scalars(statement).all())


def calculate_container_remaining(
    db: Session,
    container_id: int,
) -> Decimal:
    statement = select(StockMovement).where(
        StockMovement.container_id == container_id
    )
    movements = db.scalars(statement).all()

    return sum(
        (movement.quantity_units for movement in movements),
        Decimal("0"),
    )


def sync_container_status(
    db: Session,
    container: InsulinContainer,
) -> None:
    if container.status == ContainerStatus.DISCARDED:
        return

    remaining = calculate_container_remaining(db, container.id)

    if remaining <= 0:
        container.status = ContainerStatus.EMPTY
        return

    if remaining == container.initial_units:
        container.status = ContainerStatus.SEALED
        container.opened_at = None
        return

    container.status = ContainerStatus.OPEN

    db.flush()


def open_container(
    db: Session,
    container: InsulinContainer,
) -> None:
    if container.status == ContainerStatus.SEALED:
        container.status = ContainerStatus.OPEN
        container.opened_at = datetime.now(timezone.utc)
        db.flush()


def compute_container_expiration(
    container: InsulinContainer,
    open_validity_days: int,
    today_local: date,
) -> dict:
    if (
        container.status != ContainerStatus.OPEN
        or container.opened_at is None
    ):
        return {
            "expires_at": None,
            "days_until_expiration": None,
            "expiration_status": "not_applicable",
        }

    opened_at = container.opened_at
    if opened_at.tzinfo is None:
        opened_at = opened_at.replace(tzinfo=timezone.utc)

    opened_local_date = opened_at.astimezone(APP_TIMEZONE).date()
    expires_local_date = opened_local_date + timedelta(
        days=open_validity_days
    )

    days_until_expiration = (expires_local_date - today_local).days

    if days_until_expiration <= 0:
        expiration_status = "expired"
    elif days_until_expiration <= OPEN_EXPIRATION_WARNING_DAYS:
        expiration_status = "expiring_soon"
    else:
        expiration_status = "ok"

    expires_at = datetime.combine(
        expires_local_date,
        time.min,
        tzinfo=APP_TIMEZONE,
    )

    return {
        "expires_at": expires_at,
        "days_until_expiration": days_until_expiration,
        "expiration_status": expiration_status,
    }


def get_available_containers_fifo(
    db: Session,
    insulin_id: int,
) -> list[InsulinContainer]:
    containers = list_containers(db, insulin_id)

    open_containers = [
        container
        for container in containers
        if container.status == ContainerStatus.OPEN
    ]

    sealed_containers = [
        container
        for container in containers
        if container.status == ContainerStatus.SEALED
    ]

    return open_containers + sealed_containers
