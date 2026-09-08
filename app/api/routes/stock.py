from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models import (
    ContainerStatus,
    InsulinContainer,
    MovementType,
    StockMovement,
    User,
)
from app.schemas import (
    InsulinContainerResponse,
    StockAdjustmentCreate,
    StockInCreate,
    StockInUpdate,
    StockMovementResponse,
    StockSummaryResponse,
)
from app.services.container_service import (
    calculate_container_remaining,
    list_containers,
)
from app.services.insulin_service import (
    ensure_insulin_active,
    get_owned_insulin,
)
from app.services.stock_service import (
    InsufficientStockError,
    NoContainerAvailableError,
    apply_positive_adjustment,
    calculate_current_stock,
    create_stock_in_containers,
    distribute_negative_delta,
)


router = APIRouter(
    prefix="/api/insulins",
    tags=["stock"],
)


def _container_to_response(
    db: Session,
    container: InsulinContainer,
) -> dict:
    return {
        "id": container.id,
        "insulin_id": container.insulin_id,
        "status": container.status.value,
        "initial_units": container.initial_units,
        "remaining_units": calculate_container_remaining(
            db, container.id
        ),
        "opened_at": container.opened_at,
        "created_at": container.created_at,
    }


@router.post(
    "/{insulin_id}/stock",
    response_model=list[StockMovementResponse],
    status_code=status.HTTP_201_CREATED,
)
def add_stock(
    insulin_id: int,
    stock_data: StockInCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    insulin = get_owned_insulin(db, insulin_id, current_user)
    ensure_insulin_active(insulin)

    movements = create_stock_in_containers(
        db, insulin, stock_data.containers
    )

    db.commit()

    for movement in movements:
        db.refresh(movement)

    return movements


@router.get(
    "/{insulin_id}/stock",
    response_model=StockSummaryResponse,
)
def get_stock(
    insulin_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    insulin = get_owned_insulin(db, insulin_id, current_user)
    ensure_insulin_active(insulin)
    current_stock = calculate_current_stock(db, insulin.id)

    return {
        "insulin_id": insulin.id,
        "insulin_name": insulin.name,
        "current_stock_units": current_stock,
    }


@router.get(
    "/{insulin_id}/containers",
    response_model=list[InsulinContainerResponse],
)
def get_containers(
    insulin_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    insulin = get_owned_insulin(db, insulin_id, current_user)
    containers = list_containers(db, insulin.id)

    return [
        _container_to_response(db, container)
        for container in containers
    ]


@router.post(
    "/{insulin_id}/containers/{container_id}/discard",
    response_model=InsulinContainerResponse,
)
def discard_container(
    insulin_id: int,
    container_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    insulin = get_owned_insulin(db, insulin_id, current_user)
    ensure_insulin_active(insulin)

    container = db.scalar(
        select(InsulinContainer).where(
            InsulinContainer.id == container_id,
            InsulinContainer.insulin_id == insulin.id,
        )
    )

    if container is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Caneta/frasco não encontrado.",
        )

    if container.status == ContainerStatus.DISCARDED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Essa caneta/frasco já foi descartado.",
        )

    remaining = calculate_container_remaining(db, container.id)

    if remaining > 0:
        movement = StockMovement(
            insulin_id=insulin.id,
            container_id=container.id,
            movement_type=MovementType.DISCARD,
            quantity_units=-remaining,
            notes="Caneta/frasco descartado manualmente.",
        )
        db.add(movement)

    container.status = ContainerStatus.DISCARDED

    db.commit()
    db.refresh(container)

    return _container_to_response(db, container)


@router.post(
    "/{insulin_id}/adjustments",
    response_model=list[StockMovementResponse],
    status_code=status.HTTP_201_CREATED,
)
def adjust_stock(
    insulin_id: int,
    adjustment_data: StockAdjustmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    insulin = get_owned_insulin(db, insulin_id, current_user)
    ensure_insulin_active(insulin)

    current_stock = calculate_current_stock(db, insulin.id)
    actual_stock = adjustment_data.actual_stock_units
    difference = actual_stock - current_stock

    if difference == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "O estoque informado já é igual "
                "ao estoque calculado pelo sistema."
            ),
        )

    occurred_at = datetime.now(timezone.utc)
    notes = adjustment_data.notes.strip()

    try:
        if difference > 0:
            movements = [
                apply_positive_adjustment(
                    db, insulin, difference, occurred_at, notes
                )
            ]
        else:
            movements = distribute_negative_delta(
                db,
                insulin,
                -difference,
                MovementType.ADJUSTMENT,
                occurred_at,
                True,
                notes,
            )
    except InsufficientStockError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Não há estoque suficiente distribuído entre "
                "as canetas/frascos para aplicar esse ajuste."
            ),
        )
    except NoContainerAvailableError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Nenhuma caneta/frasco em estoque para ajustar. "
                "Adicione estoque primeiro."
            ),
        )

    db.commit()

    for movement in movements:
        db.refresh(movement)

    return movements


@router.patch(
    "/{insulin_id}/stock/{movement_id}",
    response_model=StockMovementResponse,
)
def update_stock_entry(
    insulin_id: int,
    movement_id: int,
    stock_data: StockInUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    insulin = get_owned_insulin(db, insulin_id, current_user)

    movement = db.scalar(
        select(StockMovement).where(
            StockMovement.id == movement_id,
            StockMovement.insulin_id == insulin.id,
            StockMovement.movement_type == MovementType.STOCK_IN,
        )
    )

    if movement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entrada de estoque não encontrada.",
        )

    container = movement.container

    if container.status != ContainerStatus.SEALED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Não é possível editar essa entrada: a caneta/frasco "
                "já foi aberto ou utilizado."
            ),
        )

    container.initial_units = stock_data.units
    movement.quantity_units = stock_data.units

    db.commit()
    db.refresh(movement)
    return movement
