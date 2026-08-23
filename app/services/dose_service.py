from datetime import date, datetime, time, timezone

from fastapi import HTTPException

from app.core.config import APP_TIMEZONE


def resolve_dose_datetime(
    occurred_date: date | None,
    occurred_time: time | None,
) -> tuple[datetime, bool]:
    now_local = datetime.now(APP_TIMEZONE)

    if occurred_date is None:
        return (
            now_local.astimezone(timezone.utc),
            True,
        )

    if occurred_date > now_local.date():
        raise HTTPException(
            status_code=400,
            detail="A data da aplicação não pode estar no futuro.",
        )

    if occurred_time is None:
        if occurred_date == now_local.date():
            local_datetime = now_local.replace(
                second=0,
                microsecond=0,
            )
        else:
            local_datetime = datetime.combine(
                occurred_date,
                time(12, 0),
                tzinfo=APP_TIMEZONE,
            )

        return (
            local_datetime.astimezone(timezone.utc),
            False,
        )

    clean_time = occurred_time.replace(tzinfo=None)
    local_datetime = datetime.combine(
        occurred_date,
        clean_time,
        tzinfo=APP_TIMEZONE,
    )

    if local_datetime > now_local:
        raise HTTPException(
            status_code=400,
            detail="A data e hora da aplicação não podem estar no futuro.",
        )

    return (
        local_datetime.astimezone(timezone.utc),
        True,
    )
