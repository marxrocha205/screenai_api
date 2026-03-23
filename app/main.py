"""
Ponto de entrada principal da API FastAPI.
"""
from fastapi import FastAPI
from app.core.logger import setup_logger
from app.core.database import engine, Base
from app.controllers import auth_controller, websocket_controller,chat_controller
logger = setup_logger(__name__)

# Cria as tabelas no banco de dados (Útil para testes locais sem migrações complexas agora)
Base.metadata.create_all(bind=engine)
logger.info("Tabelas do banco de dados verificadas/criadas.")

app = FastAPI(
    title="API Assistente de Acessibilidade",
    description="API para orquestração de áudio, texto e IA.",
    version="1.0.0"
)

# Inclusão dos Controladores (Rotas)
app.include_router(auth_controller.router)

@app.on_event("startup")
async def startup_event():
    """Executado quando a aplicação inicia."""
    logger.info("Iniciando a API Assistente de Acessibilidade...")

@app.get("/health")
def health_check():
    """Rota de verificação de saúde da API."""
    return {"status": "ok", "message": "API está funcionando."}

app.include_router(auth_controller.router)
app.include_router(websocket_controller.router)
app.include_router(chat_controller.router)