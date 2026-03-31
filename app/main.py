"""
Ponto de entrada principal da API ScreenAI.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


from fastapi.responses import ORJSONResponse

from app.core.logger import setup_logger
from app.core.database import AsyncSessionLocal, engine, Base
from app.core.seed import create_default_admin, seed_plans


from app.models.user_model import User
from app.models.subscription_model import Subscription
from app.models.plan_model import Plan
from app.models.chat_model import ChatSession, ChatMessage

# Importação de todos os Controladores
from app.controllers import auth_controller, websocket_controller, chat_controller, user_controller, admin_controller

logger = setup_logger(__name__)

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import traceback

app = FastAPI(
    title="API ScreenAI SaaS",
    default_response_class=ORJSONResponse
    
)

# Exception Handler Global para facilitar o Debug em produção
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"ERRO NÃO TRATADO: {str(exc)}")
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": "Erro interno do servidor.", "error_type": type(exc).__name__}
    )

# Configuração de CORS para permitir que o frontend acesse a API
# Se a lista for "*", permitimos tudo, mas sem credenciais (para evitar erro do browser)
# Se houver domínios específicos, permitimos com credenciais.
cors_origins = [o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()]
allow_all = "*" in cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins if not allow_all else ["*"],
    allow_credentials=not allow_all, # Wildcard "*" não permite credentials=True
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

app.include_router(admin_controller.router)
# -------------------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    logger.info("Iniciando a API ScreenAI...")

    # Criar tabelas (async correto)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed async
    async with AsyncSessionLocal() as db:
        await seed_plans(db)
        await create_default_admin(db)
        

    logger.info("Verificação de dados iniciais (Seed) concluída.")


@app.get("/health", tags=["Monitoramento"])
def health_check():
    """Rota de verificação de saúde para o Load Balancer (Docker/Railway)."""
    return {"status": "ok", "message": "API está funcionando."}