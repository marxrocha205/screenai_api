"""
Ponto de entrada principal da API ScreenAI.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.logger import setup_logger

# Importamos o motor async e o fallback síncrono
from app.core.database import engine, Base, SessionLocalSync
from app.core.seed import seed_plans

from app.models.user_model import User
from app.models.subscription_model import Subscription
from app.models.plan_model import Plan
from app.models.chat_model import ChatSession, ChatMessage

# Importação de todos os Controladores
from app.controllers import auth_controller, websocket_controller, chat_controller, user_controller, admin_controller

logger = setup_logger(__name__)

app = FastAPI(
    title="API ScreenAI SaaS",
    description="API de backend para orquestração multimodal (Texto, Áudio, Imagem) e gestão de assinaturas.",
    version="1.0.0"
)

# Configuração de CORS - Listagem de origens permitidas
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://frontscreenai-production.up.railway.app",
    "https://appscreenai.com",
    "https://www.appscreenai.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# -------------------------------------------------------------------
# Inclusão dos Controladores (Rotas e Endpoints)
# -------------------------------------------------------------------
app.include_router(auth_controller.router)
app.include_router(user_controller.router)
app.include_router(chat_controller.router)
app.include_router(websocket_controller.router)
app.include_router(admin_controller.router)
# -------------------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    logger.info("Iniciando a API ScreenAI...")
    
    # Criação de tabelas com SQLAlchemy Async exige este formato:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    # Executa o Seed usando a sessão Síncrona (Fallback) para não quebrar o arquivo seed.py
    db = SessionLocalSync()
    try:
        seed_plans(db)
        logger.info("Verificação de dados iniciais (Seed) concluída.")
    finally:
        db.close()

@app.get("/health", tags=["Monitoramento"])
def health_check():
    """Rota de verificação de saúde para o Load Balancer."""
    return {"status": "ok", "message": "API está funcionando."}