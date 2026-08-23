from sqlalchemy import select

from app.database import SessionLocal
from app.models import Insulin, User


def main():
    with SessionLocal() as db:
        users = db.scalars(
            select(User)
        ).all()

        if len(users) != 1:
            raise RuntimeError(
                "Esperava exatamente 1 usuário cadastrado. "
                f"Foram encontrados {len(users)}."
            )

        user = users[0]

        legacy_insulins = db.scalars(
            select(Insulin).where(
                Insulin.user_id.is_(None)
            )
        ).all()

        if not legacy_insulins:
            print("Nenhuma insulina antiga sem usuário.")
            return

        for insulin in legacy_insulins:
            insulin.user_id = user.id

            print(
                f"Vinculando '{insulin.name}' "
                f"ao usuário ID {user.id}"
            )

        db.commit()

        print(
            f"{len(legacy_insulins)} "
            "insulina(s) vinculada(s) com sucesso."
        )


if __name__ == "__main__":
    main()