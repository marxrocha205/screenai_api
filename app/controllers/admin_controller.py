"""
Controlador Administrativo.
Restrito a utilizadores com a flag is_admin=True.
Fornece métricas e agregações para o painel de controlo do frontend.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from pydantic import BaseModel
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.logger import setup_logger
from app.core.security import verify_admin_token
from app.models.user_model import User
from app.models.plan_model import Plan
from app.models.system_model import AdminAuditLog, SystemSetting
from app.models.subscription_model import Subscription
from app.models.chat_model import ChatSession, ChatMessage
from app.schemas.user_schemas import UserStatusUpdate, AdminCreditUpdate
from app.services.websocket_manager import manager

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
    
@router.get("/metrics/trends")
def get_dashboard_trends(days: int = 7, db: Session = Depends(get_db)):
    """
    Retorna dados agregados por data para a construção de gráficos de tendências.
    Por defeito, analisa os últimos 7 dias.
    """
    logger.info(f"A gerar métricas de tendências para os últimos {days} dias.")
    
    # Calcular a data de corte
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # Função Sênior (Closure): Evita repetição de código (DRY - Don't Repeat Yourself)
    # Executa a agregação diretamente no motor da Base de Dados (muito mais rápido que fazer loops em Python)
    def get_daily_counts(model):
        return (
            db.query(
                cast(model.created_at, Date).label("date"),
                func.count(model.id).label("count")
            )
            .filter(model.created_at >= cutoff_date)
            .group_by(cast(model.created_at, Date))
            .all()
        )

    # Executar as agregações para as 3 métricas principais
    users_trend = get_daily_counts(User)
    sessions_trend = get_daily_counts(ChatSession)
    messages_trend = get_daily_counts(ChatMessage)

    # Estruturar os dados para a biblioteca gráfica do Frontend (Recharts)
    # O Recharts espera um array de objetos: [{ date: "2023-10-01", users: 2, sessions: 5 }, ...]
    trends_map = {}
    
    # 1. Pré-preencher o mapa com todos os dias do intervalo (garante que dias com valor 0 aparecem no gráfico)
    for i in range(days):
        # Retroceder dia a dia a partir de hoje
        d = (datetime.utcnow() - timedelta(days=(days - 1 - i))).date()
        trends_map[d] = {
            "date": d.strftime("%d/%m"), # Formato curto para o eixo X do gráfico (ex: 24/10)
            "full_date": d.strftime("%Y-%m-%d"),
            "users": 0, 
            "sessions": 0, 
            "messages": 0
        }

    # 2. Injetar os dados reais obtidos da Base de Dados
    for row in users_trend:
        if row.date in trends_map:
            trends_map[row.date]["users"] = row.count
            
    for row in sessions_trend:
        if row.date in trends_map:
            trends_map[row.date]["sessions"] = row.count
            
    for row in messages_trend:
        if row.date in trends_map:
            trends_map[row.date]["messages"] = row.count

    # 3. Converter o dicionário numa lista ordenada pela data (do mais antigo para hoje)
    sorted_trends = sorted(trends_map.values(), key=lambda x: x["full_date"])

    return {
        "status": "success",
        "data": sorted_trends
    }
    
    
# Certifique-se de importar o novo schema no topo do ficheiro:
# from app.schemas.user_schemas import UserStatusUpdate, AdminCreditUpdate

@router.post("/users/{user_id}/credits")
def adjust_user_credits(
    user_id: int, 
    payload: AdminCreditUpdate, 
    db: Session = Depends(get_db)
):
    """
    Ajusta manualmente o saldo de créditos de um utilizador.
    Pode adicionar (valores positivos) ou deduzir (valores negativos).
    """
    logger.info(f"Admin a solicitar ajuste financeiro. Utilizador ID: {user_id} | Montante: {payload.amount} | Motivo: {payload.reason}")
    
    # 1. Obter a subscrição/conta do utilizador
    subscription = db.query(Subscription).filter(Subscription.user_id == user_id).first()
    
    if not subscription:
        logger.warning(f"Falha ao ajustar créditos: Subscrição não encontrada para o utilizador ID {user_id}.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Conta de faturação não encontrada para este utilizador."
        )

    # 2. Calcular o novo saldo (prevenindo saldos negativos acidentais se for uma dedução)
    novo_saldo = subscription.remaining_credits + payload.amount
    if novo_saldo < 0:
         raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Operação inválida. O utilizador tem apenas {subscription.remaining_credits} créditos. Não é possível deduzir {abs(payload.amount)}."
        )

    # 3. Aplicar a mutação
    subscription.remaining_credits = novo_saldo
    
    try:
        db.commit()
        db.refresh(subscription)
        
        # Num sistema real, aqui chamaríamos um serviço de Auditoria para guardar o 'payload.reason'
        logger.info(f"Sucesso. Novo saldo do utilizador ID {user_id}: {subscription.remaining_credits}. Motivo registado: {payload.reason}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Erro crítico na base de dados ao ajustar créditos do ID {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Ocorreu um erro interno ao processar a transação financeira."
        )

    return {
        "status": "success",
        "message": "Créditos ajustados com sucesso.",
        "data": {
            "user_id": user_id,
            "new_balance": subscription.remaining_credits,
            "reason": payload.reason
        }
    }
    
@router.get("/billing")
def get_billing_data(limit: int = 100, db: Session = Depends(get_db)):
        """
        Retorna a lista completa de utilizadores com os seus dados financeiros cruzados.
        Substitui a simulação do frontend por dados reais e auditáveis.
        """
        logger.info("Admin a consultar as de faturação e créditos.")
        
        # Realizamos um LEFT JOIN para garantir que utilizadores sem assinatura
        # também aparecem no painel (para podermos injetar créditos neles se necessário)
        results = (
            db.query(
                User.id,
                User.email,
                User.is_active,
                User.is_admin,
                Subscription.status.label("subscription_status"),
                Subscription.remaining_credits,
                Plan.name.label("plan_name")
            )
            .outerjoin(Subscription, Subscription.user_id == User.id)
            .outerjoin(Plan, Plan.id == Subscription.plan_id)
            .order_by(User.created_at.desc())
            .limit(limit)
            .all()
        )

        data = []
        for row in results:
            # Tratamento defensivo (Fallback) caso o utilizador não tenha registo financeiro
            plan_name = row.plan_name if row.plan_name else ("Enterprise" if row.is_admin else "Free")
            status = row.subscription_status if row.subscription_status else ("active" if row.is_active else "inactive")
            credits = row.remaining_credits if row.remaining_credits is not None else 0

            data.append({
                "id": row.id,
                "email": row.email,
                "plan_name": plan_name,
                "subscription_status": status,
                "remaining_credits": credits
            })

        return {
            "status": "success",
            "data": data
        }        

@router.get("/websockets/stats")
def get_ws_stats():
    """Retorna o estado atual do servidor de WebSockets."""
    stats = manager.get_active_stats()
    return {
        "status": "success",
        "data": stats
    } 


class SettingUpdate(BaseModel):
    value: str

@router.get("/audit")
def get_audit_logs(limit: int = 100, db: Session = Depends(get_db)):
    """Retorna os registos de auditoria mais recentes."""
    logs = (
        db.query(AdminAuditLog, User.email.label("admin_email"))
        .join(User, User.id == AdminAuditLog.admin_id)
        .order_by(AdminAuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    
    results = []
    for log, email in logs:
        results.append({
            "id": log.id,
            "admin_email": email,
            "action": log.action,
            "target_entity": log.target_entity,
            "target_id": log.target_id,
            "details": log.details,
            "created_at": log.created_at
        })
    return {"status": "success", "data": results}

@router.get("/settings")
def get_system_settings(db: Session = Depends(get_db)):
    """Lista as configurações dinâmicas globais."""
    settings = db.query(SystemSetting).all()
    return {
        "status": "success", 
        "data": [{"key": s.key, "value": s.value, "description": s.description, "updated_at": s.updated_at} for s in settings]
    }

@router.patch("/settings/{key}")
def update_system_setting(key: str, payload: SettingUpdate, db: Session = Depends(get_db)):
    """Atualiza o valor de uma configuração em tempo real."""
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not setting:
        raise HTTPException(status_code=404, detail="Configuração não encontrada.")
    
    setting.value = payload.value
    
    # REGISTO DE AUDITORIA AUTOMÁTICO!
    # Nota: Precisará do ID do admin logado. Assumindo que o `Depends(verify_admin_token)` devolve o utilizador, 
    # se não, use um ID genérico para já ou ajuste para injetar o `current_user`.
    # audit_log = AdminAuditLog(admin_id=current_user.id, action="UPDATE_SETTING", ...)
    
    db.commit()
    return {"status": "success", "message": "Configuração atualizada."}