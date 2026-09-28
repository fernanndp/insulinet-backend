import re
import unicodedata


MIN_PASSWORD_LENGTH = 15
MAX_PASSWORD_LENGTH = 128


COMMON_PASSWORDS = {
    "123456789012345",
    "1234567890123456",
    "passwordpassword",
    "password123456",
    "senha1234567890",
    "minhasenha123456",
    "qwertyuiopasdfg",
    "qwertyuiopasdfgh",
    "adminadminadmin",
    "administrador123",
    "insulinet123456",
    "insulinet2026",
}


def _normalize(value: str) -> str:
    return unicodedata.normalize(
        "NFKC",
        value,
    ).casefold()


def _simplify(value: str) -> str:
    normalized = _normalize(value)

    return re.sub(
        r"[^a-z0-9]",
        "",
        normalized,
    )


def validate_password_strength(
    password: str,
    *,
    name: str | None = None,
    email: str | None = None,
) -> None:

    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            "A senha deve ter pelo menos 15 caracteres."
        )

    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError(
            "A senha deve ter no máximo 128 caracteres."
        )

    normalized = _normalize(password)
    simplified = _simplify(password)

    if not simplified:
        raise ValueError(
            "Escolha uma senha mais difícil de adivinhar."
        )

    if (
        normalized.strip() in COMMON_PASSWORDS
        or simplified in COMMON_PASSWORDS
    ):
        raise ValueError(
            "Essa senha é muito comum. "
            "Escolha uma senha mais difícil de adivinhar."
        )

    # Impede senhas formadas apenas por números.
    if simplified.isdigit():
        raise ValueError(
            "A senha não pode ser formada apenas por números."
        )

    # Ex.: aaaaaaaaaaaaaaa
    if len(set(normalized.replace(" ", ""))) <= 2:
        raise ValueError(
            "Essa senha é muito repetitiva."
        )

    # Ex.: abcabcabcabcabc
    repeated_pattern = re.fullmatch(
        r"(.{1,4})\1{3,}",
        normalized.replace(" ", ""),
    )

    if repeated_pattern:
        raise ValueError(
            "Essa senha possui um padrão muito previsível."
        )

    weak_patterns = (
        "123456789",
        "987654321",
        "qwerty",
        "asdfgh",
        "password",
    )

    if (
        len(simplified) <= 20
        and any(
            pattern in simplified
            for pattern in weak_patterns
        )
    ):
        raise ValueError(
            "Essa senha possui uma sequência muito previsível."
        )

    if (
        "insulinet" in simplified
        and len(simplified) <= 20
    ):
        raise ValueError(
            "Evite usar o nome Insulinet na senha."
        )

    personal_terms: list[str] = []

    if name:
        for part in name.split():
            term = _simplify(part)

            if len(term) >= 4:
                personal_terms.append(term)

    if email:
        email_prefix = email.split("@")[0]
        email_term = _simplify(email_prefix)

        if len(email_term) >= 4:
            personal_terms.append(email_term)

    simple_suffixes = {
        "",
        "123",
        "1234",
        "12345",
        "123456",
        "2025",
        "2026",
        "2027",
    }

    for term in personal_terms:

        if not simplified.startswith(term):
            continue

        suffix = simplified[len(term):]

        if suffix in simple_suffixes:
            raise ValueError(
                "A senha é muito parecida com "
                "seu nome ou e-mail."
            )