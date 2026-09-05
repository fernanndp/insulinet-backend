from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ContainerStatus, InsulinContainer, StockMovement


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
