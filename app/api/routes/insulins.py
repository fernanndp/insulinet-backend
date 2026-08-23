from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models import Insulin, StockMovement, User
from app.schemas import (
    InsulinCreate,
    InsulinResponse,
    InsulinSummaryResponse,
    InsulinUpdate,
    StockHistoryItem,
)
from app.services.insulin_service import get_owned_insulin
from app.services.projection_service import build_insulin_summary


router = APIRouter(
    prefix="/api/insulins",
    tags=["insulins"],
)


@router.post(
    "",
    response_model=InsulinResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_insulin(
    insulin_data: InsulinCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    insulin = Insulin(
        user_id=current_user.id,
        name=insulin_data.name,
        concentration_units_per_ml=insulin_data.concentration_units_per_ml,
        container_volume_ml=insulin_data.container_volume_ml,
    )

    db.add(insulin)
    db.commit()
    db.refresh(insulin)
    return insulin


@router.get(
    "",
    response_model=list[InsulinResponse],
)
def list_insulins(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    statement = (
        select(Insulin)
        .where(Insulin.user_id == current_user.id)
        .order_by(Insulin.id)
    )
    return db.scalars(statement).all()


@router.get(
    "/{insulin_id}/history",
    response_model=list[StockHistoryItem],
)
def get_history(
    insulin_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    insulin = get_owned_insulin(db, insulin_id, current_user)

    statement = (
        select(StockMovement)
        .where(StockMovement.insulin_id == insulin.id)
        .order_by(
            StockMovement.occurred_at.desc(),
            StockMovement.id.desc(),
        )
    )
    return db.scalars(statement).all()


@router.get(
    "/{insulin_id}/summary",
    response_model=InsulinSummaryResponse,
)
def get_insulin_summary(
    insulin_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    insulin = get_owned_insulin(db, insulin_id, current_user)
    return build_insulin_summary(db, insulin)


@router.patch(
    "/{insulin_id}",
    response_model=InsulinResponse,
)
def update_insulin(
    insulin_id: int,
    insulin_data: InsulinUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    insulin = get_owned_insulin(db, insulin_id, current_user)
    clean_name = insulin_data.name.strip()

    if not clean_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O nome da insulina não pode ficar vazio.",
        )

    insulin.name = clean_name
    insulin.concentration_units_per_ml = (
        insulin_data.concentration_units_per_ml
    )
    insulin.container_volume_ml = insulin_data.container_volume_ml
    insulin.active = insulin_data.active

    db.commit()
    db.refresh(insulin)
    return insulin
