"""
Controlador Administrativo.
Restrito a utilizadores com a flag is_admin=True.
Fornece métricas e agregações para o painel de controlo do frontend.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.core.logger import setup_logger
from app.core.security import verify_admin_token
from app.models.user_model import User
from app.models.subscription_model import Subscription
from app.models.chat_model import ChatSession, ChatMessage
from app.schemas.user_schemas import UserStatusUpdate

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

router.patch("/users/{user_id}/status")
def update_user_status(
    user_id: int, 
    payload: UserStatusUpdate, 
    db: Session = Depends(get_db)
):
    """
    Atualiza o estado (ativo/inativo) de um utilizador específico.
    Ação restrita a administradores.
    """
    logger.info(f"Admin a solicitar alteração de estado para o utilizador ID: {user_id}. Novo estado: {payload.is_active}")
    
    # 1. Procurar o utilizador na base de dados
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        logger.warning(f"Falha na alteração: Utilizador ID {user_id} não encontrado.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Utilizador não encontrado no sistema."
        )
    
    # Regra de negócio opcional, mas recomendada: impedir que um admin se desative a si próprio
    # if user.is_admin:
    #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não pode desativar outro administrador.")

    # 2. Atualizar o registo
    user.is_active = payload.is_active
    
    try:
        db.commit()
        db.refresh(user)
        logger.info(f"Estado do utilizador ID {user_id} atualizado com sucesso para {user.is_active}.")
    except Exception as e:
        db.rollback()
        logger.error(f"Erro na base de dados ao atualizar o utilizador ID {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Ocorreu um erro interno ao guardar as alterações."
        )

    return {
        "status": "success",
        "message": "Estado do utilizador atualizado com sucesso.",
        "data": {
            "id": user.id,
            "is_active": user.is_active
        }
    }