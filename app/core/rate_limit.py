from fastapi import Request
from fastapi.responses import JSONResponse

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


def get_client_ip(
    request: Request,
) -> str:
    forwarded_for = request.headers.get(
        "x-forwarded-for"
    )

    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    return get_remote_address(request)


limiter = Limiter(
    key_func=get_client_ip
)


async def rate_limit_exceeded_handler(
    request: Request,
    exc: RateLimitExceeded,
):
    return JSONResponse(
        status_code=429,
        content={
            "detail": (
                "Muitas tentativas foram realizadas. "
                "Aguarde um pouco e tente novamente."
            )
        },
    )