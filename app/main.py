"""
Ponto de entrada principal da API FastAPI.
"""
from fastapi import FastAPI
from app.core.logger import setup_logger

logger = setup_logger(__name__)

app = FastAPI(
    title="API Assistente de Acessibilidade",
    description="API para orquestração de áudio, texto e IA.",
    version="1.0.0"
)

@app.on_event("startup")
async def startup_event():
    """Executado quando a aplicação inicia."""
    logger.info("Iniciando a API Assistente de Acessibilidade...")

@app.get("/health")
def health_check():
    """
    Rota de verificação de saúde da API.
    Utilizada pela Railway para garantir que o contêiner está rodando corretamente.
    """
    logger.info("Health check acessado.")
    return {"status": "ok", "message": "API está funcionando."}