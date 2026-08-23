from urllib.parse import urlencode

import resend

from app.core.config import EMAIL_FROM, FRONTEND_URL, RESEND_API_KEY


resend.api_key = RESEND_API_KEY


def send_password_reset_email(
    recipient_email: str,
    token: str,
) -> None:
    query = urlencode({"token": token})
    reset_url = (
        f"{FRONTEND_URL.rstrip('/')}"
        f"/reset-password?{query}"
    )

    params: resend.Emails.SendParams = {
        "from": EMAIL_FROM,
        "to": [recipient_email],
        "subject": "Recuperação de senha - Insulinet",
        "html": f"""
        <div>
            <h2>Recuperação de senha</h2>
            <p>Recebemos uma solicitação para alterar a senha da sua conta.</p>
            <p><a href="{reset_url}">Alterar minha senha</a></p>
            <p>Este link expira em 30 minutos.</p>
        </div>
        """,
    }

    resend.Emails.send(params)
