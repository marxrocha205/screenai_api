"""
Controlador de rotas REST para Chat e Uploads Multimodais.
Permite o envio de texto, áudio, imagens pesadas e documentos PDF via HTTP POST,
integrando-se ao mesmo histórico de conversa (Redis) utilizado pelo WebSocket.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Request
from typing import Optional
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.logger import setup_logger
from app.core.security import verify_ws_token # Reutilizamos a validação do token JWT
from app.services.gemini_service import gemini_service
from app.services.stt_service import stt_service
from app.services.redis_service import redis_service
from app.models.chat_model import ChatSession, ChatMessage

logger = setup_logger(__name__)
router = APIRouter(prefix="/api/chat", tags=["Chat Multimodal REST"])

# Rota protegida por autenticação (Passa o token no cabeçalho ou na query)
@router.post("/message")
async def send_multimodal_message(
    token: str,
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    """
    Recebe uma mensagem de texto e/ou um arquivo (Áudio, PDF, Imagem).
    Processa e retorna a resposta da IA.
    """
    # Valida o usuário
    user = verify_ws_token(token)
    logger.info(f"Requisição HTTP Multimodal recebida do usuário {user.id}")
    is_allowed = await redis_service.check_rate_limit(user.id, max_requests=10, window_seconds=60)
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitos pedidos. Por favor, aguarde um minuto."
        )
        
    if not text and not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="É necessário enviar texto ou um arquivo."
        )

    uploaded_files_refs = []

    # Processamento do arquivo (se existir)
    if file:
        try:
            # Lê os bytes do arquivo enviado pelo usuário
            file_bytes = await file.read()
            mime_type = file.content_type
            filename = file.filename
            
            logger.info(f"Processando arquivo: {filename} ({mime_type})")
            
            # Validação básica de segurança para tipos permitidos
            tipos_permitidos = [
                "application/pdf", 
                "audio/mpeg", 
                "audio/wav", 
                "audio/ogg", 
                "image/jpeg", 
                "image/png"
            ]
            
            if mime_type not in tipos_permitidos:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail=f"Tipo de arquivo não suportado. Envie PDF, Imagens ou Áudio."
                )

            # Faz o upload para a infraestrutura do Gemini
            gemini_file_ref = await gemini_service.upload_file_to_gemini(
                file_bytes=file_bytes, 
                mime_type=mime_type, 
                file_name=filename
            )
            uploaded_files_refs.append(gemini_file_ref)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Erro ao processar upload HTTP: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erro ao processar o arquivo enviado."
            )

    # Envia os dados (texto e referências de arquivos) para a IA
    resposta_ia = await gemini_service.generate_response(
        user_id=user.id,
        user_message=text or "",
        uploaded_files=uploaded_files_refs
    )

    # Retorna o JSON com a resposta da IA (A API REST retorna JSON padrão, não precisa gerenciar websocket aqui)
    return {
        "status": "success",
        "user_id": user.id,
        "response": resposta_ia
    }

@router.post("/transcribe")
async def transcribe_voice(
    token: str,
    audio_file: UploadFile = File(...)
):
    """
    Rota REST exclusiva para transcrição de áudio.
    Recebe um arquivo de voz e devolve o texto, sem chamar o Gemini.
    """
    user = verify_ws_token(token)
    logger.info(f"Requisição de transcrição REST recebida do usuário {user.id}")
    is_allowed = await redis_service.check_rate_limit(user.id, max_requests=5, window_seconds=60)
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Limite de transcrições de voz atingido. Aguarde um minuto."
        )
    # Validação simples de tipo de arquivo
    if not audio_file.content_type.startswith("audio/"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="O arquivo enviado não é um formato de áudio válido."
        )

    try:
        file_bytes = await audio_file.read()
        
        # Pega a extensão do arquivo original (ex: .mp3, .wav, .webm)
        extensao = f".{audio_file.filename.split('.')[-1]}" if "." in audio_file.filename else ".webm"
        
        texto_transcrito = await stt_service.transcribe_audio_file(file_bytes, suffix=extensao)
        
        return {
            "status": "success",
            "user_id": user.id,
            "text": texto_transcrito
        }
    except Exception as e:
        logger.error(f"Erro na rota de transcrição: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao transcrever o áudio."
        )  
@router.get("/sessions")
async def get_chat_sessions(request: Request, db: Session = Depends(get_db)):
    """
    Busca real no PostgreSQL: Retorna a lista de todas as conversas do utilizador.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token ausente ou inválido.")
    
    token = auth_header.split(" ")[1]
    user = verify_ws_token(token)
    
    # Busca todas as sessões do utilizador, ordenadas pela mais recente
    sessions = db.query(ChatSession).filter(ChatSession.user_id == user["id"]).order_by(ChatSession.updated_at.desc()).all()
    
    return [
        {
            "id": s.id, 
            "title": s.title, 
            "created_at": s.created_at, 
            "updated_at": s.updated_at
        } for s in sessions
    ]

@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, request: Request, db: Session = Depends(get_db)):
    """
    Busca real no PostgreSQL: Retorna as mensagens de uma conversa específica.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token ausente ou inválido.")
    
    token = auth_header.split(" ")[1]
    user = verify_ws_token(token)

    # 1. Verifica se a sessão existe e se pertence a este utilizador (Segurança)
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == user["id"]).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada ou não pertence ao utilizador.")
    
    # 2. Busca todas as mensagens desta sessão, em ordem cronológica
    messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc()).all()
    
    return [
        {
            "id": m.id, 
            "role": m.role, 
            "content": m.content
        } for m in messages
    ]        