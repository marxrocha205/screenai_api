"""
Controlador Administrativo.
Restrito a utilizadores com a flag is_admin=True.
Fornece métricas e agregações para o painel de controlo do frontend.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.core.logger import setup_logger
from app.core.security import verify_admin_token
from app.models.user_model import User
from app.models.subscription_model import Subscription
from app.models.chat_model import ChatSession, ChatMessage

logger = setup_logger(__name__)

# O parâmetro dependencies aplica a validação de segurança a TODAS as rotas deste router
router = APIRouter(
    prefix="/api/admin", 
    tags=["Painel de Administração"],
    dependencies=[Depends(verify_admin_token)]
)

@router.get("/metrics")
def get_dashboard_metrics(db: Session = Depends(get_db)):
    """
    Retorna os KPIs (Key Performance Indicators) globais do sistema.
    Utiliza funções de agregação nativas do SQL para alta performance.
    """
    logger.info("A gerar métricas do painel de administração.")
    
    # 1. Total de utilizadores registados
    total_users = db.query(func.count(User.id)).scalar() or 0
    
    # 2. Total de conversas (Sessões)
    total_sessions = db.query(func.count(ChatSession.id)).scalar() or 0
    
    # 3. Total de mensagens transacionadas na plataforma
    total_messages = db.query(func.count(ChatMessage.id)).scalar() or 0
    
    # 4. Total de créditos remanescentes (Passivo da plataforma)
    total_credits_liability = db.query(func.sum(Subscription.remaining_credits)).scalar() or 0

    return {
        "status": "success",
        "data": {
            "total_users": total_users,
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "total_credits_in_circulation": total_credits_liability
        }
    }

@router.get("/chats/recent")
def get_recent_system_activity(limit: int = 50, db: Session = Depends(get_db)):
    """
    Retorna os metadados das conversas mais recentes da plataforma.
    Por conformidade com privacidade, NÃO retorna o conteúdo das mensagens (ChatMessage.content),
    apenas os dados da sessão (títulos e datas).
    """
    recent_sessions = (
        db.query(
            ChatSession.id, 
            ChatSession.title, 
            ChatSession.created_at,
            User.email
        )
        .join(User, User.id == ChatSession.user_id)
        .order_by(ChatSession.created_at.desc())
        .limit(limit)
        .all()
    )

    # Mapeamento do resultado SQLAlchemy para uma lista de dicionários
    results = [
        {
            "session_id": session.id,
            "title": session.title,
            "user_email": session.email,
            "created_at": session.created_at
        }
        for session in recent_sessions
    ]

    return {"status": "success", "data": results}

@router.get("/users")
def get_all_users(limit: int = 100, db: Session = Depends(get_db)):
    """
    Retorna a lista de utilizadores registados na plataforma.
    """
    logger.info("A listar utilizadores para o painel de admin.")
    users = db.query(
        User.id, 
        User.email, 
        User.is_active, 
        User.is_admin, 
        User.created_at
    ).order_by(User.created_at.desc()).limit(limit).all()

    results = [
        {
            "id": u.id,
            "email": u.email,
            "is_active": u.is_active,
            "is_admin": u.is_admin,
            "created_at": u.created_at
        }
        for u in users
    ]
    return {"status": "success", "data": results}

@router.get("/sessions")
def get_all_sessions(limit: int = 100, db: Session = Depends(get_db)):
    """
    Retorna uma lista detalhada de sessões para a aba de gestão.
    """
    sessions = (
        db.query(
            ChatSession.id, 
            ChatSession.title, 
            ChatSession.created_at,
            User.email
        )
        .join(User, User.id == ChatSession.user_id)
        .order_by(ChatSession.created_at.desc())
        .limit(limit)
        .all()
    )

    results = [
        {
            "session_id": s.id,
            "title": s.title,
            "user_email": s.email,
            "created_at": s.created_at
        }
        for s in sessions
    ]
    return {"status": "success", "data": results}