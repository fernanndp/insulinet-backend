from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Insulin, User


def get_owned_insulin(
    db: Session,
    insulin_id: int,
    current_user: User,
) -> Insulin:
    insulin = db.scalar(
        select(Insulin).where(
            Insulin.id == insulin_id,
            Insulin.user_id == current_user.id,
        )
    )

    if insulin is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insulina não encontrada.",
        )

    return insulin


def ensure_insulin_active(insulin: Insulin) -> None:
    if not insulin.active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Esta insulina está inativa. "
                "Ative-a novamente para registrar novas movimentações."
            ),
        )
