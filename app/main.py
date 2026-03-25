"""
Ponto de entrada principal da API ScreenAI.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.logger import setup_logger
from app.core.database import SessionLocal, engine, Base
from app.core.seed import seed_plans


from app.models.user_model import User
from app.models.subscription_model import Subscription
from app.models.plan_model import Plan
from app.models.chat_model import ChatSession, ChatMessage

# Importação de todos os Controladores
from app.controllers import auth_controller, websocket_controller, chat_controller, user_controller

logger = setup_logger(__name__)

app = FastAPI(
    title="API ScreenAI SaaS",
    description="API de backend para orquestração multimodal (Texto, Áudio, Imagem) e gestão de assinaturas.",
    version="1.0.0"
)

# Configuração de CORS para permitir que o frontend local acesse a API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, substitua pelo domínio real do seu frontend (ex: "https://meuscreenai.com")
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------------
# Inclusão dos Controladores (Rotas e Endpoints)
# -------------------------------------------------------------------
# Rotas públicas de autenticação (/auth/register, /auth/login)
app.include_router(auth_controller.router)

# Rotas privadas da API (/api/users/me, /api/chat/message, etc)
app.include_router(user_controller.router)
app.include_router(chat_controller.router)

# Rota do WebSocket (o prefixo já foi definido dentro do websocket_controller.py)
app.include_router(websocket_controller.router)
# -------------------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    logger.info("Iniciando a API ScreenAI...")
    Base.metadata.create_all(bind=engine)
    # Executa o Seed dos dados obrigatórios de planos financeiros
    db = SessionLocal()
    try:
        seed_plans(db)
        logger.info("Verificação de dados iniciais (Seed) concluída.")
    finally:
        db.close()

@app.get("/health", tags=["Monitoramento"])
def health_check():
    """Rota de verificação de saúde para o Load Balancer (Docker/Railway)."""
    return {"status": "ok", "message": "API está funcionando."}