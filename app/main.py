"""
Ponto de entrada principal da API ScreenAI.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.logger import setup_logger
from app.controllers import auth_controller, websocket_controller, chat_controller

logger = setup_logger(__name__)

app = FastAPI(
    title="API ScreenAI",
    description="API para orquestração de áudio, texto e IA conversacional multimodal.",
    version="1.0.0"
)

# Configuração de CORS para permitir que o frontend local acesse a API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, substitua pelo domínio real do seu frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclusão dos Controladores (Rotas)
app.include_router(auth_controller.router)
app.include_router(websocket_controller.router)
app.include_router(chat_controller.router)

@app.on_event("startup")
async def startup_event():
    logger.info("Iniciando a API ScreenAI...")

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "API está funcionando."}