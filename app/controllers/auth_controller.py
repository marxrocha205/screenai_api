"""
Controlador de Autenticação.
Gerencia as rotas de registro de usuários e login (geração de token).
Refatorado para operações assíncronas não-bloqueantes (SQLAlchemy 2.0).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logger import setup_logger
from app.core.security import get_password_hash, verify_password, create_access_token
from app.models.user_model import User
from app.models.plan_model import Plan
from app.models.subscription_model import Subscription
from app.schemas.user_schemas import UserCreate, UserResponse, Token

logger = setup_logger(__name__)
router = APIRouter(prefix="/auth", tags=["Autenticação"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Registra um novo usuário no sistema vinculando-o ao plano padrão (Free).
    """
    logger.info(f"Tentativa de registro assíncrono para o email: {user.email}")
    
    # 1. Verifica se o email já existe
    result_user = await db.execute(select(User).where(User.email == user.email))
    db_user = result_user.scalars().first()
    
    if db_user:
        logger.warning(f"Falha de registro: Email {user.email} já cadastrado.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email já registrado no sistema."
        )
    
    try:
        # 2. Busca o plano Free no catálogo
        result_plan = await db.execute(select(Plan).where(Plan.name == "Free"))
        free_plan = result_plan.scalars().first()
        
        if not free_plan:
            logger.error("Plano 'Free' não encontrado na base de dados. Falha crítica.")
            raise HTTPException(status_code=500, detail="Erro de configuração do sistema.")

        # 3. Cria o novo utilizador
        hashed_pw = get_password_hash(user.password)
        new_user = User(email=user.email, hashed_password=hashed_pw)
        db.add(new_user)
        
        # Dica de Engenharia (flush): 
        # await db.flush() envia o SQL para o banco (gerando o ID), mas não finaliza a transação.
        await db.flush() 
        
        # 4. Cria a Assinatura vinculando o ID do Utilizador ao ID do Plano
        new_subscription = Subscription(
            user_id=new_user.id,
            plan_id=free_plan.id,
            status="active",
            remaining_credits=free_plan.monthly_credits
        )
        db.add(new_subscription)
        
        # 5. Consolida tudo (Utilizador + Assinatura) de forma atômica
        await db.commit()
        await db.refresh(new_user)
        
        logger.info(f"Utilizador {user.email} registado com plano Free (ID: {new_user.id})")
        return new_user
        
    except HTTPException:
        raise
    except Exception as e:
        # Importante: rollback também é uma operação de I/O de rede com o banco, logo é await
        await db.rollback()
        logger.error(f"Erro na base de dados ao registar utilizador: {str(e)}")
        raise HTTPException(status_code=500, detail="Erro interno ao registar utilizador.")


@router.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: AsyncSession = Depends(get_db)
):
    """
    Autentica o utilizador e gera o token JWT enriquecido com dados de negócio (user_id, plan_id).
    """
    logger.info(f"Tentativa de login para o utilizador: {form_data.username}")
    
    # 1. Busca o utilizador no banco
    result_user = await db.execute(select(User).where(User.email == form_data.username))
    user = result_user.scalars().first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning(f"Falha de login: Credenciais inválidas para {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Busca a assinatura do utilizador para injetar no Token
    result_sub = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    subscription = result_sub.scalars().first()
    plan_id = subscription.plan_id if subscription else None
    
    # ENRIQUECIMENTO DO PAYLOAD
    access_token = create_access_token(
        data={
            "sub": user.email,
            "user_id": user.id,
            "plan_id": plan_id
        }
    )
    
    logger.info(f"Login bem-sucedido para {user.email}. Token gerado.")
    return {"access_token": access_token, "token_type": "bearer"}