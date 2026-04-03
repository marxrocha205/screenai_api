"""
Ponto de entrada principal da API ScreenAI.
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.logger import setup_logger

# Importamos o motor async e as configurações de banco
from app.core.database import engine, Base
from app.core.seed import seed_data  # <-- Novo seed 100% assíncrono

# Importação de todos os Controladores
from app.controllers import (
    auth_controller, 
    websocket_controller, 
    chat_controller, 
    user_controller, 
    admin_controller,
    payment_controller # <-- NOVA ROTA ALPHAPAY
)

# Importação do Serviço de Cron
from app.services.cron_service import start_daily_cron

logger = setup_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerenciador de Ciclo de Vida da Aplicação (Padrão FastAPI Moderno).
    Substitui o antigo @app.on_event("startup").
    """
    logger.info("🚀 Iniciando a API ScreenAI...")
    
    # 1. Criação de tabelas com SQLAlchemy Async
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    # 2. Executa o Seed usando a NOVA função Assíncrona
    await seed_data()
    logger.info("✅ Verificação de dados iniciais (Seed) concluída.")
    
    # 3. Inicia o Fiscal Automático de Pagamentos (Cron Job) em background
    asyncio.create_task(start_daily_cron())
    
    yield
    
    # Executado ao desligar o servidor
    logger.info("🛑 Desligando a API ScreenAI...")

app = FastAPI(
    title="API ScreenAI SaaS",
    description="API de backend para orquestração multimodal e gestão de assinaturas.",
    version="1.0.0",
    lifespan=lifespan
)

# Configuração de CORS - Listagem de origens permitidas (MANTIDO DO SEU CÓDIGO)
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://frontscreenai-production.up.railway.app",
    "https://appscreenai.com",
    "https://www.appscreenai.com",
    "https://frontscreenai-copy-production.up.railway.app",
    "https://www.frontscreenai-copy-production.up.railway.app"
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
app.include_router(payment_controller.router)  # <-- ROTA ALPHAPAY ADICIONADA
# -------------------------------------------------------------------

@app.get("/health", tags=["Monitoramento"])
def health_check():
    """Rota de verificação de saúde para o Load Balancer."""
    return {"status": "ok", "message": "API está funcionando."}