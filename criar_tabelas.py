from app.core.database import engine, Base
# Importar os modelos OBRIGA o SQLAlchemy a registá-los
from app.models.user_model import User
from app.models.subscription_model import Subscription
from app.models.plan_model import Plan
from app.models.chat_model import ChatSession, ChatMessage

print("Iniciando a criação forçada de tabelas...")

# O 'create_all' olha para todos os modelos importados acima e cria as tabelas no DB
Base.metadata.create_all(bind=engine)

print("✅ Tabelas criadas com sucesso (ou já existiam).")