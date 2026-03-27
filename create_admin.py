# create_admin.py
from app.core.database import SessionLocal
from app.core.seed import create_default_admin
# IMPORTANTE: Importar todos os modelos para o SQLAlchemy resolver os relacionamentos
from app.models.user_model import User
from app.models.plan_model import Plan
from app.models.subscription_model import Subscription
import sys

def main():
    db = SessionLocal()
    try:
        # A função de seed agora terá os mappers prontos
        create_default_admin(db)
        print("Operação finalizada com sucesso.")
    except Exception as e:
        print(f"Erro ao criar admin: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()