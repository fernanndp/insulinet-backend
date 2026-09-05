from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Insulin, InsulinContainer, MovementType, StockMovement
from app.services.container_service import (
    calculate_container_remaining,
    get_available_containers_fifo,
    open_container,
    sync_container_status,
)


class InsufficientStockError(Exception):
    def __init__(self, missing_units: Decimal):
        self.missing_units = missing_units
        super().__init__(
            "Estoque insuficiente entre as canetas/frascos disponíveis."
        )


class NoContainerAvailableError(Exception):
    def __init__(self):
        super().__init__(
            "Nenhuma caneta/frasco em estoque para essa operação."
        )


def calculate_current_stock(
    db: Session,
    insulin_id: int,
) -> Decimal:
    statement = select(
        func.coalesce(
            func.sum(StockMovement.quantity_units),
            0,
        )
    ).where(
        StockMovement.insulin_id == insulin_id
    )

    result = db.scalar(statement)
    return Decimal(result)


def create_stock_in_containers(
    db: Session,
    insulin: Insulin,
    containers_count: int,
) -> list[StockMovement]:
    units_per_container = (
        insulin.concentration_units_per_ml
        * insulin.container_volume_ml
    )

    movements: list[StockMovement] = []

    for _ in range(containers_count):
        container = InsulinContainer(
            insulin_id=insulin.id,
            initial_units=units_per_container,
        )
        db.add(container)
        db.flush()

        movement = StockMovement(
            insulin_id=insulin.id,
            container_id=container.id,
            movement_type=MovementType.STOCK_IN,
            quantity_units=units_per_container,
            notes="Entrada de 1 recipiente",
        )
        db.add(movement)
        db.flush()
        movements.append(movement)

    return movements


def distribute_negative_delta(
    db: Session,
    insulin: Insulin,
    units: Decimal,
    movement_type: MovementType,
    occurred_at: datetime,
    occurred_time_known: bool,
    notes: str | None,
) -> list[StockMovement]:
    remaining_to_deduct = units
    movements: list[StockMovement] = []

    for container in get_available_containers_fifo(db, insulin.id):
        if remaining_to_deduct <= 0:
            break

        container_remaining = calculate_container_remaining(
            db, container.id
        )

        if container_remaining <= 0:
            sync_container_status(db, container)
            continue

        open_container(db, container)

        take = min(remaining_to_deduct, container_remaining)

        movement = StockMovement(
            insulin_id=insulin.id,
            container_id=container.id,
            movement_type=movement_type,
            quantity_units=-take,
            occurred_at=occurred_at,
            occurred_time_known=occurred_time_known,
            notes=notes,
        )
        db.add(movement)
        db.flush()
        movements.append(movement)

        remaining_to_deduct -= take
        sync_container_status(db, container)

    if remaining_to_deduct > 0:
        raise InsufficientStockError(remaining_to_deduct)

    if len(movements) > 1:
        anchor_id = movements[0].id
        for movement in movements[1:]:
            movement.group_id = anchor_id
        db.flush()

    return movements


def apply_positive_adjustment(
    db: Session,
    insulin: Insulin,
    units: Decimal,
    occurred_at: datetime,
    notes: str | None,
) -> StockMovement:
    containers = get_available_containers_fifo(db, insulin.id)

    if not containers:
        raise NoContainerAvailableError()

    container = containers[0]
    open_container(db, container)

    movement = StockMovement(
        insulin_id=insulin.id,
        container_id=container.id,
        movement_type=MovementType.ADJUSTMENT,
        quantity_units=units,
        occurred_at=occurred_at,
        occurred_time_known=True,
        notes=notes,
    )
    db.add(movement)
    db.flush()

    sync_container_status(db, container)

    return movement
